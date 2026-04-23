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
from sofia_utils.printing import ( print_ind,
                                   print_sep )
from wa_agents.agent import Agent
from wa_agents.basemodels import *
from wa_agents.case_handler_base import ( CaseHandlerBase,
                                          CH_State,
                                          TransitionDK )
from wa_agents.whatsapp_functions import markdown_to_whatsapp

from domain_knowledge.dk_basemodels import RCImageAnalysis
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
    
    # =====================================================================================
    # STATE MACHINE DEFINITION, CONSTRUCTOR AND RESET METHOD
    # =====================================================================================
    
    @classmethod
    def define_state_machine_config(cls) \
    -> tuple[ list[ CH_State ], str, list[ dict[ TransitionDK, str] ] ] :
        """
        Define state machine states and transitions. \\
        Returns:
            * List of states. Each must have `name`. Optional: `on_enter`, `while_in`, `on_exit`.
            * List of transitions as dicts with keys `source`, `trigger` and `dest`.
            * Initial state name.
        
        NOTE:
            * Lists `on_enter` / `on_exit` are true FSM callbacks and should only contain
              methods that must run when a transition changes state.
            * List `while_in` contains response-generation actions that
              `generate_response()` dispatches manually while the handler remains in
              the current state.
            * Because `auto_transitions = False`, ingesting a message can leave the
              machine in the same state without re-running `on_enter`. That is why
              `ask_for_*` and `call_*_agent` live in `while_in`.
            * If we instead forced same-state transitions with
              `auto_transitions = True`, we would also need to account for that
              state's `on_exit` + `on_enter` firing on every such loop.
        """
        states = [
        
        # Information-gathering states
        CH_State(
            "idle",
            while_in = [ "ask_for_model_having_nothing" ],
        ),
        CH_State(
            "have_model_no_image",
            on_enter = [ "set_model_if_necessary" ],
            while_in = [ "ask_for_image" ],
        ),
        CH_State(
            "have_image_no_model",
            while_in = [ "ask_for_model_having_image" ],
        ),
        
        # Single-task agents
        CH_State(
            "image_agent",
            on_enter = [ "set_model_if_necessary" ],
            while_in = [ "call_image_agent" ],
            on_exit  = [ "clear_image_agent_context" ],
        ),
        CH_State(
            "match_agent",
            while_in = [ "call_match_agent" ],
            on_exit  = [ "clear_match_agent_context" ],
        ),
        
        # Main agent
        CH_State(
            "main_agent",
            while_in = [ "call_main_agent" ],
        ),
        
        ]
        
        initial = "idle"
        
        transitions = [
        
        # From state: idle
        { "source"  : "idle",
          "trigger" : "has_model_choice",
          "dest"    : "have_model_no_image" },
        { "source"  : "idle",
          "trigger" : "has_image",
          "dest"    : "have_image_no_model" },
        
        # From state: have_model_no_image
        { "source"  : "have_model_no_image",
          "trigger" : "has_image",
          "dest"    : "image_agent" },
        
        # From state: have_image_no_model
        { "source"  : "have_image_no_model",
          "trigger" : "has_model_choice",
          "dest"    : "image_agent" },
        
        # From state: image_agent
        { "source"  : "image_agent",
          "trigger" : "has_image_analysis",
          "dest"    : "match_agent" },
        
        # From state: match_agent
        { "source"  : "match_agent",
          "trigger" : "has_match_tool_call",
          "dest"    : "main_agent" },
        
        # From state: main_agent
        { "source"  : "main_agent",
          "trigger" : "has_image",
          "dest"    : "image_agent" },
        
        ]
        
        return states, initial, transitions
    
    def __init__( self,
                  operator : WhatsAppMetaData,
                  user     : WhatsAppContact,
                  debug    : bool = False ) -> None :
        
        super().__init__( operator, user, debug)
        
        # Drone model choice
        self.model_choice : str | None = None
        
        # Agents
        self.image_agent : Agent = None
        self.match_agent : Agent = None
        self.main_agent  : Agent = None
        
        # Agent contexts
        self.image_agent_context : list[Message] = []
        self.match_agent_context : list[Message] = []
        self.main_agent_context  : list[Message] = []
        
        # Images cache (for image agent)
        self.imgs_cache : dict[ str, bytes] = {}
        
        # Initialize state machine from method `define_state_machine_config`
        self.init_machine()
        
        # Tool server
        self.tool_server = ToolServer(debug)
        
        return
    
    def reset_state_machine(self) -> None :
        
        self.state = "idle"
        self.model_choice = None
        self.image_agent_context.clear()
        self.match_agent_context.clear()
        self.main_agent_context.clear()
        
        return
    
    # =====================================================================================
    # METHOD OVERLOADS
    # =====================================================================================
    
    def context_build( self, truncate : bool = True) -> None :
        """
        Build context. \\
        Overloads method `CaseHandlerBase.context_build` by calling the original method and then initializing the Domain Knowledge Database (DKDB). \\
        Args:
            truncate: Whether or not to enforce the max content length
        """
        
        super().context_build(truncate)
        
        # Initialize DKDB
        if (
        self.case_manifest and self.case_manifest.model
        and ( not self.tool_server.dkdb.model )
        ) :
            self.tool_server.dkdb.set_model(self.case_manifest.model)
        
        return
    
    def ingest_message( self, message : Message) -> None :
        """
        Ingest a single message and fire corresponding triggers \\
        Overloads no-op method `CaseHandlerBase.ingest_message`. \\
        Args:
            message : Instance of a subclass of Message
        """
        
        # ---------------------------------------------------------------------------------
        # BEFORE TRANSITION
        
        if self.debug :
            print_sep()
            print("State Machine Message Ingestion")
            print_ind( f"[>] State k-1: {self.state}", 1)
        
        msg_has_image = False
        
        # ---------------------------------------------------------------------------------
        # TRANSITION HAPPENS HERE
        
        if isinstance( message, UserMsg) :
            
            if isinstance( message, UserInteractiveReplyMsg) :
                self.model_choice = message.choice.id
                self.trigger("has_model_choice")
            
            msg_has_image = isinstance( message, UserContentMsg) and message.media \
                            and message.media.mime.startswith("image")
            if msg_has_image :
                self.trigger("has_image")
        
        elif isinstance( message, AssistantMsg) :
            
            if message.agent == "image" :
                self.trigger("has_image_analysis")
            
            elif ( message.agent == "match" ) and message.tool_calls :
                self.trigger("has_match_tool_call")
        
        # ---------------------------------------------------------------------------------
        # AFTER TRANSITION
        
        if self.debug :
            print_ind( f"[>] State k  : {self.state}", 1)
        
        # If message is meant for the user eyes only then return
        if isinstance( message, ServerMsg) and message.user_eyes :
            return
        
        # Else append message to corresponding agent's context
        elif self.state in ( 'idle',
                             'have_model_no_image',
                             'have_image_no_model',
                             'image_agent') and msg_has_image :
            self.image_agent_context.append(message)
        
        elif self.state == 'match_agent' :
            self.match_agent_context.append(message)
        
        elif self.state == 'main_agent' :
            self.main_agent_context.append(message)
        
        return
    
    # =====================================================================================
    # ON ENTER AND ON EXIT METHODS
    # =====================================================================================
    
    def clear_image_agent_context(self) -> None :
        return self.image_agent_context.clear()
    
    def clear_match_agent_context(self) -> None :
        return self.match_agent_context.clear()
    
    def set_model_if_necessary(self) -> None :
        
        if (
        ( not ( self.case_manifest.model and self.tool_server.dkdb.model ) )
        and ( self.model_choice and isinstance( self.model_choice, str) )
        and ( self.model_choice in self.tool_server.dkdb.MODELS_AVAILABLE )
        ) :
            if not self.case_manifest.model :
                self.case_manifest.model = self.model_choice
                self.storage.manifest_write(self.case_manifest)
        
            if not self.tool_server.dkdb.model :
                    self.tool_server.dkdb.set_model(self.model_choice)
        
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
            msg_reply      = ServerTextMsg( origin = _orig_,
                                            text   = system_message.get("body") )
            msg_reply.print()
            
            # Send reply message to user
            self.send_text(msg_reply)
            # Write reply message to storage and update manifest
            self.context_update(msg_reply)
            
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
        
        # Retrieve manually-dispatched actions from current state
        state   = self.machine.get_state(self.state)
        actions = getattr( state, "while_in", [] )
        
        for action in actions :
            
            if action == "ask_for_model_having_nothing" :
                return self.ask_user_for("model_having_nothing")
            
            elif action == "ask_for_model_having_image" :
                return self.ask_user_for("model_having_image")
            
            elif action == "ask_for_image" :
                return self.ask_user_for("image")
            
            elif action == "call_image_agent" :
                return self.call_image_agent(max_tokens)
            
            elif action == "call_match_agent" :
                return self.call_match_agent(max_tokens)
            
            elif action == "call_main_agent" :
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
                                                type    = "button",
                                                header  = msg_header,
                                                body    = msg_body,
                                                options = msg_options )
            message.print()
            
            # Send message to user
            self.send_interactive(message)
            # Write message to storage and update manifest and state machine
            self.context_update(message)
        
        elif argument == "image" :
            
            system_message = self.load_system_message("ask_for_image.json")
            message        = ServerTextMsg( origin = _orig_,
                                            text   = system_message.get("body") )
            message.print()
            
            # Send message to user
            self.send_text(message)
            # Write message to storage and update manifest and state machine
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
        image_agent_context = self.image_agent_context
        # Prepare images cache
        for msg_with_image in image_agent_context :
            image_filename = msg_with_image.media.name
            if image_filename not in self.imgs_cache :
                image_content = self.storage.media_get(image_filename)
                self.imgs_cache[image_filename] = image_content
        
        # Generate response
        message = self.image_agent.get_response( context    = image_agent_context,
                                                 origin     = f"{_orig_}/stage-1",
                                                 load_imgs  = True,
                                                 imgs_cache = self.imgs_cache,
                                                 output_st  = RCImageAnalysis,
                                                 max_tokens = max_tokens,
                                                 debug      = self.debug )
        
        # If the agent did not respond then simply return False
        if not message or message.is_empty() :
           return False
        
        # DEBUG: Print message
        message.print()
        # If debug mode is on then send message to human
        self.send_text(message) if self.debug else None
        # Write message to storage and update manifest and state machine
        self.context_update(message)
        
        # ---------------------------------------------------------------------------------
        # PHASE 2: INJECT MESSAGE FOR MATCH AGENT
        
        # Retrive data from Domain Knowledge Database
        data_str = self.tool_server.dkdb.list_messages()
        # Construct message
        msg_with_data = ServerTextMsg( origin = f"{_orig_}/stage-2",
                                       text   = data_str )
        msg_with_data.print()
        # DEBUG: Send message to human
        self.send_text(msg_with_data) if self.debug else None
        # Write message to storage and update manifest and state machine
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
        match_agent_context = self.match_agent_context
        
        # Generate response
        message = self.match_agent.get_response( context    = match_agent_context,
                                                 origin     = f"{_orig_}/stage-1",
                                                 max_tokens = max_tokens,
                                                 debug      = self.debug )
        
        # If the agent did not respond then simply return False
        if not message or message.is_empty() :
           return False
        
        # DEBUG: Print message
        message.print()
        # If message contains text or debug mode is on then send message to human
        if message.text or self.debug :
            self.send_text(message)
        # Write message to storage and update manifest and state machine
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
                                      tool_results = tool_results )
            message.print()
            # DEBUG: Send message to human
            self.send_text(message)
            # Write message to storage and update manifest and state machine
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
        main_agent_context = self.main_agent_context
        
        # Generate main agent response
        message = self.main_agent.get_response( context    = main_agent_context,
                                                origin     = f"{_orig_}/stage-1",
                                                max_tokens = max_tokens,
                                                debug      = self.debug )
        
        # If the agent did not respond then simply return False
        if not message or message.is_empty() :
           return False
        
        # DEBUG: Print message
        message.print()
        # Send message to user
        self.send_text(message)
        # Write message to storage and update manifest and state machine
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
        # Process low level tool calls
        tool_results = self.tool_server.process(message.tool_calls)
        
        # Process tool results
        if tool_results :
            # Construct message
            message = ToolResultsMsg( origin       = f"{_orig_}/stage-2",
                                      tool_results = tool_results )
            message.print()
            # DEBUG: Send message to human
            self.send_text(message)
            # Write message to storage and update manifest and state machine
            self.context_update(message)
        
        # If case remains open then signal need for another response
        return bool( self.case_manifest.status == "open" )
    
    # =====================================================================================
    # OTHER HELPERS
    # =====================================================================================
    
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
            message = ServerTextMsg( origin    = _orig_,
                                     text      = message_text,
                                     user_eyes = True )
            message.print()
            # Send message to human
            self.send_text(message)
            # Write message to storage and update manifest and state machine
            self.context_update(message)
        
        return
