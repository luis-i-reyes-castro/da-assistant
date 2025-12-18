"""
Case Handler
-----
* Decide whether an incoming human message belongs to the first case,
  the same open case, or a new case (based on explicit close or staleness).
* Store human and AI messages while maintaining clean, idempotent storage
  with per-user locking.
* Build a token-budget-friendly case_context to feed to your main agent.
* Mark cases as resolved.
"""

from inspect import currentframe

from sofia_utils.io import load_json_file
from wa_agents.agent import Agent
from wa_agents.basemodels import *
from wa_agents.casehandlerbase import CaseHandlerBase
from wa_agents.whatsapp_functions import markdown_to_whatsapp

from dk_basemodels import RCImageAnalysis
from state_machine import StateMachine
from tool_server import ToolServer


class CaseHandler(CaseHandlerBase) :
    """
    Class for message ingestion and agent orchestration.
    Relies on CaseHandlerBase for management of cases, context and message sending.
    """
    
    MAIN_AGENT_MODELS  = [ "openai/gpt-5-mini",
                           "qwen/qwen2.5-vl-32b-instruct:free" ]
    IMAGE_AGENT_MODELS = [ "openai/gpt-5-nano",
                           "qwen/qwen2.5-vl-32b-instruct:free",
                           "mistralai/pixtral-12b" ]
    
    def __init__( self,
                  operator : WhatsAppMetaData,
                  user     : WhatsAppContact,
                  debug    : bool = False ) -> None :
        
        super().__init__( operator, user, debug)
        
        self.state_machine = StateMachine()
        self.tool_server   = ToolServer()
        
        self.triggers   = {}
        self.imgs_cache = {}
        
        self.image_agent = None
        self.match_agent = None
        self.main_agent  = None
        
        if self.debug :
            self.state_machine.debug    = True
            self.tool_server.dkdb.debug = True
        
        return
    
    def case_set_drone_model( self, drone_model : str | None) -> None :
        
        if drone_model and isinstance( drone_model, str) and \
           drone_model in self.tool_server.dkdb.MODELS_AVAILABLE :
            
            self.case_manifest.model = drone_model
            self.storage.manifest_write(self.case_manifest)
        
        return
    
    def load_system_message( self, json_file : str) -> dict[ str, str] :
        
        file_dict : dict = load_json_file(f"agent_prompts/{json_file}")
        data_dict : dict = file_dict.get(self.user_data.code_lan)
        if not data_dict :
            data_dict = file_dict.get("en")
        
        return data_dict
    
    def send_agent_update( self, message_name : str) -> None :
        
        _orig_ = f"{self.__class__.__name__}/{currentframe().f_code.co_name}"
        
        # Fetch agent update messages
        agent_updates : dict = self.load_system_message("agent_updates.json")
        message_text  : str  = agent_updates.get(message_name)
        if message_text :
            # Construct message
            message = ServerTextMsg( origin  = _orig_,
                                     case_id = self.case_id,
                                     text    = message_text,
                                     user_eyes = True )
            message.print()
            # Send message to human
            self.send_text(message)
            # Write message to storage and update manifest and triggers
            self.context_update(message)
        
        return
    
    # =====================================================================================
    # METHOD OVERLOADS
    # =====================================================================================
    
    def context_build( self, truncate : bool = True) -> None :
        """
        Build context
        Args:
            truncate: Whether or not to enforce the max content length
            debug:    Debug mode flag
        """
        
        super().context_build(truncate)
        
        # Initialize DKDB
        if self.case_manifest and self.case_manifest.model \
                              and ( not self.tool_server.dkdb.model ) :
            self.tool_server.dkdb.set_model(self.case_manifest.model)
        
        # Process for triggers
        self.triggers = self.state_machine.process(self.case_context)
        
        return
    
    def context_update( self,
                        message  : Message,
                        triggers : bool = True ) -> None :
        
        super().context_update(message)
        
        # Update triggers
        if triggers :
            self.triggers = self.state_machine.update(message)
        
        return
    
    # =====================================================================================
    # PROCESS MESSAGE FROM HUMAN
    # =====================================================================================

    def process_message( self,
                         message       : WhatsAppMsg,
                         media_content : MediaContent | None = None
                       ) -> bool :
        
        _orig_ = f"{self.__class__.__name__}/{currentframe().f_code.co_name}"
        
        # Dedup and ingest message
        msg = self.dedup_and_ingest_message( message, media_content)
        
        # If media is image then store contents in images cache
        if msg and isinstance( msg, UserContentMsg) \
        and msg.media and msg.media.mime.startswith("image") :
            
            self.imgs_cache[msg.media.name] = media_content.content
        
        # If user message is not text, image, interactive reply then reply with a
        # message indicating lack of support
        if message.type not in ( "text", "image", "interactive") :
            
            system_message = self.load_system_message("unsupported.json")
            msg_reply      = ServerTextMsg( origin  = _orig_,
                                            case_id = self.case_id,
                                            text    = system_message.get("body") )
            msg_reply.print()
            
            # Send reply message to user
            self.send_text(msg_reply)
            # Write reply message to storage and update manifest
            self.context_update( msg_reply, triggers = False)
            
            # Signal need to wait for user's reply
            return False
        
        # Signal need to generate a response
        return True if msg else False
    
    # =====================================================================================
    # GENERATE RESPONSE AS A FUNCTION OF FSM STATE
    # =====================================================================================
    
    def generate_response( self,
                           max_tokens : int | None = None ) -> bool :
        
        # If necessary then build context
        if not self.case_context :
            self.context_build()
        
        # Perform action according to trigger
        
        if self.triggers["set_model"] :
            if not self.tool_server.dkdb.model :
                model = self.state_machine.model_choice
                self.case_set_drone_model(model)
                self.tool_server.dkdb.set_model(model)
        
        if self.triggers["ask_for_model_having_nothing"] :
            return self.ask_user_for("model_having_nothing")
        
        elif self.triggers["ask_for_model_having_image"] :
            return self.ask_user_for("model_having_image")
        
        elif self.triggers["ask_for_image"] :
            return self.ask_user_for("image")
        
        elif self.triggers["call_image_agent"] :
            return self.call_image_agent(max_tokens)
        
        elif self.triggers["call_match_agent"] :
            return self.call_match_agent(max_tokens)
        
        elif self.triggers["call_main_agent"] :
            return self.call_main_agent(max_tokens)
        
        return False
    
    def ask_user_for( self, argument : str) -> bool :
        
        _orig_ = f"{self.__class__.__name__}/{currentframe().f_code.co_name}"
        
        if argument.startswith("model") :
            
            # Prepare header/body
            system_message = self.load_system_message("ask_for_model.json")
            msg_header     = system_message.get("title")
            msg_body       = None
            match argument :
                case "model_having_nothing" :
                    msg_body = system_message.get("body") + "\n\n" \
                             + system_message.get("nothing")
                case "model_having_image" :
                    msg_body = system_message.get("body") + "\n\n" \
                             + system_message.get("image")
                case _ :
                    e_msg = f"Invalid argument {argument}"
                    raise ValueError(f"In class CaseHandler method ask_user_for: {e_msg}")
            
            # Retrieve drone model options
            msg_options = self.tool_server.dkdb.get_model_options()
            
            # Construct message
            message = ServerInteractiveOptsMsg( origin  = _orig_,
                                                case_id = self.case_id,
                                                type    = "button",
                                                header  = msg_header,
                                                body    = msg_body,
                                                options = msg_options )
            message.print()
            
            # Send message to user
            self.send_interactive(message)
            # Write message to storage and update manifest and triggers
            self.context_update(message)
        
        elif argument == "image" :
            
            system_message = self.load_system_message("ask_for_image.json")
            message        = ServerTextMsg( origin  = _orig_,
                                            case_id = self.case_id,
                                            text    = system_message.get("body") )
            message.print()
            
            # Send message to user
            self.send_text(message)
            # Write message to storage and update manifest and triggers
            self.context_update(message)
        
        else :
            raise ValueError(f"In {_orig_}: Invalid argument {argument}")
        
        # Return False because we need to wait for user to reply
        return False
    
    # =====================================================================================
    # SETUP AND CALL IMAGE ANALYSIS AGENT
    # =====================================================================================
    
    def setup_image_agent(self) -> None :
        
        self.image_agent = Agent( "image", self.IMAGE_AGENT_MODELS)
        
        drone_model = self.tool_server.dkdb.model
        self.image_agent.load_prompts([f"agent_prompts/image_{drone_model}.md"])
        
        return
    
    def call_image_agent( self, max_tokens : int | None = None) -> bool :
        # ---------------------------------------------------------------------------------
        # Send agent update to user
        self.send_agent_update("image_start")
        
        # ---------------------------------------------------------------------------------
        # Set text for message origin field
        _orig_ = f"{self.__class__.__name__}/{currentframe().f_code.co_name}"
        
        # If necessary then setup agent
        if not self.image_agent :
            self.setup_image_agent()
        
        # ---------------------------------------------------------------------------------
        # PHASE 1: GENERATE IMAGE ANALYSIS
        
        # Prepare image analysis agent context
        image_agent_context = self.state_machine.image_agent_context
        # Prepare images cache
        for msg_with_image in image_agent_context :
            image_filename = msg_with_image.media.name
            if image_filename not in self.imgs_cache :
                image_content = self.storage.media_get(image_filename)
                self.imgs_cache[image_filename] = image_content
        
        # Generate response
        ag_resp_obj = self.image_agent.get_response( context    = image_agent_context,
                                                     load_imgs  = True,
                                                     imgs_cache = self.imgs_cache,
                                                     output_st  = RCImageAnalysis,
                                                     max_tokens = max_tokens,
                                                     debug      = self.debug )
        
        # If the agent did not respond then do not store response and return False
        if not ag_resp_obj or ag_resp_obj.is_empty() :
           return False
        
        # Construct message
        message = AssistantMsg.from_content( origin  = f"{_orig_}/stage-1",
                                             case_id = self.case_id,
                                             content = ag_resp_obj )
        message.print()
        
        # DEBUG: Send message to human
        self.send_text(message) if self.debug else None
        # Write message to storage and update manifest and triggers
        self.context_update(message)
        
        # ---------------------------------------------------------------------------------
        # PHASE 2: INJECT MESSAGE FOR MATCH AGENT
        
        # Retrive data from Domain Knowledge Database
        data_str = self.tool_server.dkdb.list_messages()
        # Construct message
        msg_with_data = ServerTextMsg( origin  = f"{_orig_}/stage-2",
                                       case_id = self.case_id,
                                       text    = data_str )
        msg_with_data.print()
        # DEBUG: Send message to human
        self.send_text(msg_with_data) if self.debug else None
        # Write message to storage and update manifest and triggers
        self.context_update(msg_with_data)
        
        # ---------------------------------------------------------------------------------
        # Send agent update to user
        # self.send_agent_update( "image_end", debug)
        
        # ---------------------------------------------------------------------------------
        # Signal need for another response
        return True
    
    # =====================================================================================
    # SETUP AND CALL MATCH AGENT
    # =====================================================================================
    
    def setup_match_agent(self) -> None :
        
        self.match_agent = Agent( "match", self.MAIN_AGENT_MODELS)
        
        match_ag_prompts = [ { "path"    : "agent_prompts/match.md",
                               "replace" : {} },
                             { "path"    : "agent_prompts/user_profile.md",
                               "replace" : { "{COUNTRY}"  : self.user_data.country,
                                             "{LANGUAGE}" : self.user_data.language } },
                             { "path"    : "agent_prompts/spanish.md",
                               "replace" : {} } ]
        match_ag_tools   = [ f"agent_tools/match_{self.match_agent.api}.json" ]
        
        self.match_agent.load_prompts(match_ag_prompts)
        self.match_agent.load_tools(match_ag_tools)
        self.match_agent.post_processors.append(markdown_to_whatsapp)
        
        return
    
    def call_match_agent( self, max_tokens : int | None = None) -> bool :
        # ---------------------------------------------------------------------------------
        # Send agent update to user
        # self.send_agent_update( "match_start", debug)
        
        # ---------------------------------------------------------------------------------
        # Set text for message origin field
        _orig_ = f"{self.__class__.__name__}/{currentframe().f_code.co_name}"
        
        # If necessary then setup agent
        if not self.match_agent :
            self.setup_match_agent()
        
        # ---------------------------------------------------------------------------------
        # STAGE 1: GENERATE INITIAL MATCH AGENT RESPONSE
        
        # Prepare match agent context
        match_agent_context = self.state_machine.match_agent_context
        
        # Generate response
        ag_resp_obj = self.match_agent.get_response( context    = match_agent_context,
                                                     load_imgs  = False,
                                                     max_tokens = max_tokens,
                                                     debug      = self.debug )
        
        # If the agent did not respond then do not store response and return False
        if not ag_resp_obj or ag_resp_obj.is_empty() :
           return False
        
        # Construct message
        message = AssistantMsg.from_content( origin  = f"{_orig_}/stage-1",
                                             case_id = self.case_id,
                                             content = ag_resp_obj )
        message.print()
        
        # If message contains text then send message to human
        self.send_text(message) if ( message.text or self.debug ) else None
        # Write message to storage and update manifest and triggers
        self.context_update(message)
        
        # If there are no tool calls then there is no need for more responses
        if not message.tool_calls :
            return False
        
        # ---------------------------------------------------------------------------------
        # STAGE 2: PROCESS TOOL CALLS, WRITE RESULTS TO CONTEXT, AND RETURN TRUE.
        
        tool_results = self.tool_server.process(message.tool_calls)
        if tool_results :
            # Construct message
            message = ToolResultsMsg( origin       = f"{_orig_}/stage-2",
                                      case_id      = self.case_id,
                                      tool_results = tool_results )
            message.print()
            # DEBUG: Send message to human
            self.send_text(message)
            # Write message to storage and update manifest and triggers
            self.context_update(message)
        
        # ---------------------------------------------------------------------------------
        # Send agent update to user
        # self.send_agent_update( "match_end", debug)
        
        # ---------------------------------------------------------------------------------
        # Signal need for another response
        return True
    
    # =====================================================================================
    # SETUP AND CALL MAIN AGENT
    # =====================================================================================
    
    def setup_main_agent(self) -> None :
        
        self.main_agent = Agent( "main", self.MAIN_AGENT_MODELS)
        
        drone_model     = self.tool_server.dkdb.model
        main_ag_prompts = [ { "path"    : f"agent_prompts/main_{drone_model}.md",
                              "replace" : {} },
                            { "path"    : "agent_prompts/user_profile.md",
                              "replace" : { "{COUNTRY}"  : self.user_data.country,
                                            "{LANGUAGE}" : self.user_data.language } },
                            { "path"    : "agent_prompts/spanish.md",
                              "replace" : {} } ]
        main_ag_tools   = [ f"agent_tools/main_{self.main_agent.api}.json" ]
        
        self.main_agent.load_prompts(main_ag_prompts)
        self.main_agent.load_tools(main_ag_tools)
        self.main_agent.post_processors.append(markdown_to_whatsapp)
        
        return
    
    def call_main_agent( self, max_tokens : int | None = None) -> bool :
        """
        Generate AI response
        Args:
            debug: Enable debug output for API interactions
        Returns: True if we need to generate more responses, else False.
        """
        # ---------------------------------------------------------------------------------
        # Send agent update to user
        # self.send_agent_update( "main_start", debug)
        
        # ---------------------------------------------------------------------------------
        # Set text for message origin field
        _orig_ = f"{self.__class__.__name__}/{currentframe().f_code.co_name}"
        
        # ---------------------------------------------------------------------------------
        # STAGE 1: GENERATE INITIAL MAIN AGENT RESPONSE
        
        # If necessary then setup agent
        if not self.main_agent :
            self.setup_main_agent()
        
        # Prepare main agent context
        main_agent_context = self.state_machine.main_agent_context
        
        # Generate main agent response
        ag_resp_obj = self.main_agent.get_response( context    = main_agent_context,
                                                    load_imgs  = False,
                                                    max_tokens = max_tokens,
                                                    debug      = self.debug )
        
        # If the agent did not respond then do not store response and return False
        # TODO: Add retries with a threshold on the number of retries.
        if not ag_resp_obj or ag_resp_obj.is_empty() :
           return False
        
        # Construct message
        message = AssistantMsg.from_content( origin  = f"{_orig_}/stage-1",
                                             case_id = self.case_id,
                                             content = ag_resp_obj )
        message.print()
        
        # Send message to user
        self.send_text(message)
        # Write message to storage and update manifest and triggers
        self.context_update(message)
        
        # If there are no tool calls then there is no need for more responses
        if not message.tool_calls :
            return False
        
        # ---------------------------------------------------------------------------------
        # STAGE 2: PROCESS TOOL CALLS, WRITE RESULTS TO CONTEXT, AND RETURN TRUE.
        
        # Process high level tool calls
        for tc in message.tool_calls :
            if tc.name == "mark_as_resolved" :
                self.case_mark_as_resolved()
            if tc.name == "set_model" :
                model = tc.input.get("model")
                self.case_set_drone_model(model)
        # Process low level tool calls
        tool_results = self.tool_server.process(message.tool_calls)
        
        # Process tool results
        if tool_results :
            # Construct message
            message = ToolResultsMsg( origin       = f"{_orig_}/stage-2",
                                      case_id      = self.case_id,
                                      tool_results = tool_results )
            message.print()
            # DEBUG: Send message to human
            self.send_text(message)
            # Write message to storage and update manifest and triggers
            self.context_update(message)
        
        # If case remains open then signal need for another response
        return bool( self.case_manifest.status == "open" )
