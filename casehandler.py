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

from pathlib import Path
from uuid import UUID

from sofia_utils.io import load_json_file
from sofia_utils.printing import (
    get_qualname as here,
    print_ind,
    print_sep,
)
from wa_agents.agent import AsyncAgent
from wa_agents.case_handler_base import (
    AsyncWhatsAppCaseHandler,
    CaseHandlerState,
    TransitionDict,
)
from wa_agents.case_handler_models import (
    AssistantMsg,
    CaseManifest,
    HumanServerMsg,
    HumanUserContentMsg,
    HumanUserInteractiveReplyMsg,
    HumanUserMsg,
    Message,
    ServerInteractiveOptsMsg,
    ServerMsg,
    ServerTextMsg,
    ToolResultsMsg,
)
from wa_agents.supabase import (
    WhatsAppDatabaseRecord_Business,
    WhatsAppDatabaseRecord_Contact,
)
from wa_agents.whatsapp_functions import markdown_to_whatsapp
from wa_agents.whatsapp_models import WhatsAppMessage

from .domain_knowledge.dk_basemodels import RCImageAnalysis
from .tool_server import ToolServer


class CaseHandler (AsyncWhatsAppCaseHandler) :
    """
    Class for message ingestion and agent orchestration.
    Relies on AsyncWhatsAppCaseHandler for cases, context, and message sending.
    """
    
    HANDLER_KEY        = "da-assistant"
    PACKAGE_DIR        = Path(__file__).resolve().parent
    AGENT_NAMES        = ( "image", "match", "main" )
    
    MAIN_AGENT_MODELS  = [ "openai/gpt-5-mini",
                           "qwen/qwen2.5-vl-32b-instruct:free" ]
    IMAGE_AGENT_MODELS = [ "openai/gpt-5-nano",
                           "qwen/qwen2.5-vl-32b-instruct:free",
                           "mistralai/pixtral-12b" ]
    
    # =====================================================================================
    # STATE MACHINE DEFINITION, CONSTRUCTOR AND RESET METHOD
    # =====================================================================================
    
    @classmethod
    def define_state_machine_config(cls) -> tuple[
        list[CaseHandlerState],
        str,
        list[TransitionDict],
    ] :
        """
        Define state machine states and transitions.
        For more information on this method see `CaseHandlerBase`.
        """
        states = [
        
        # Initial state
        CaseHandlerState("idle"),

        # Information-gathering states
        CaseHandlerState(
            "have_nothing",
            while_in = [ "ask_for_model_having_nothing" ],
        ),
        CaseHandlerState(
            "have_model_no_image",
            while_in = [ "ask_for_image" ],
        ),
        CaseHandlerState(
            "have_image_no_model",
            while_in = [ "ask_for_model_having_image" ],
        ),
        
        # Single-task agents
        CaseHandlerState(
            "image_agent",
            while_in = [ "call_image_agent" ],
        ),
        CaseHandlerState(
            "match_agent",
            while_in = [ "call_match_agent" ],
        ),
        
        # Main agent
        CaseHandlerState(
            "main_agent",
            while_in = [ "call_main_agent" ],
        ),
        
        ]
        
        initial = "idle"
        
        transitions = [
        
        # From state: idle
        { "source"  : "idle",
          "trigger" : "has_text_only",
          "dest"    : "have_nothing" },
        { "source"  : "idle",
          "trigger" : "has_image",
          "dest"    : "have_image_no_model" },
        
        # From state: have_nothing
        { "source"  : "have_nothing",
          "trigger" : "has_model_choice",
          "dest"    : "have_model_no_image" },
        { "source"  : "have_nothing",
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
    
    def __init__(
        self,
        business : WhatsAppDatabaseRecord_Business,
        contact  : WhatsAppDatabaseRecord_Contact,
        *,
        api_inbound_msg_id : int | None        = None,
        handler_id         : int | None        = None,
        owner_token        : UUID | str | None = None,
        debug              : bool              = False,
        database_url       : str | None        = None,
    ) -> None :
        
        super().__init__(
            business,
            contact,
            api_inbound_msg_id = api_inbound_msg_id,
            handler_id         = handler_id,
            owner_token        = owner_token,
            debug              = debug,
            database_url       = database_url,
        )
        
        # Drone model choice
        self.model_choice : str | None = None
        
        # Agents
        self.image_agent : AsyncAgent | None = None
        self.match_agent : AsyncAgent | None = None
        self.main_agent  : AsyncAgent | None = None
        
        # Initialize state machine from method `define_state_machine_config`
        self.init_machine()
        
        # Tool server
        self.tool_server = ToolServer(debug)
        
        return
    
    def reset_state_machine(self) -> None :
        
        self.state = "idle"
        self.model_choice = None
        self.agent_contexts["image"].clear()
        self.agent_contexts["match"].clear()
        self.agent_contexts["main"].clear()
        
        return

    def _machine_state(self) -> str | None :
        """
        Serialize the FSM state and selected drone model into one database field.
        """
        state = super()._machine_state()
        
        if state and self.model_choice :
            return f"{state},{self.model_choice}"
        
        return state
    
    def _restore_machine_state( self, manifest : CaseManifest) -> None :
        """
        Restore the FSM state and drone model from the persisted composite value.
        """
        persisted = manifest.machine_state
        if not persisted :
            return
        
        parts = persisted.split(",")
        if ( len(parts) > 2 ) or any( not part for part in parts ) :
            raise ValueError(f"In {here()}: Invalid machine state '{persisted}'")
        
        state = parts[0]
        model = parts[1] if len(parts) == 2 else None
        
        if ( not self.machine ) or ( state not in self.machine.states ) :
            raise ValueError(f"In {here()}: Invalid FSM state '{state}'")
        
        if model :
            self.model_choice = model
            self.ensure_model_loaded()
        
        self.machine.set_state(state)
        
        return
    
    async def apply_message_to_state_machine(
        self,
        message : Message,
    ) -> None :
        """
        Apply a single message to handler state and fire corresponding triggers. \\
        Overloads the no-op method on `AsyncWhatsAppCaseHandler`. \\
        Args:
            message : Instance of a subclass of Message
        """
        
        # ---------------------------------------------------------------------------------
        # BEFORE TRANSITION
        
        if self.debug :
            print_sep()
            print("State Machine Message Ingestion")
            print_ind( f"[>] State k-1: {self.state}", 1)

        if isinstance( message, HumanServerMsg) :
            return
        
        msg_has_image = False
        
        # ---------------------------------------------------------------------------------
        # TRANSITION HAPPENS HERE
        
        if isinstance( message, HumanUserMsg) :
            
            if (
                isinstance( message, HumanUserInteractiveReplyMsg) and
                ( self.state in ( "have_nothing", "have_image_no_model") )
            ) :
                self.model_choice = self.validate_model_choice(message.choice.id)
                await self.trigger("has_model_choice")
            
            msg_has_image = bool(
                isinstance( message, HumanUserContentMsg) and
                message.media                             and
                message.media.mime.startswith("image")
            )
            if msg_has_image :
                await self.trigger("has_image")
            elif (
                isinstance( message, HumanUserContentMsg) and
                message.text and ( self.state == "idle" )
            ) :
                await self.trigger("has_text_only")
        
        elif isinstance( message, AssistantMsg) :
            
            if (
                ( message.agent == "image" ) and
                await self.trigger("has_image_analysis")
            ) :
                self.agent_context_clear("image")
            
            elif (
                ( message.agent == "match" ) and
                message.tool_calls            and
                await self.trigger("has_match_tool_call")
            ) :
                self.agent_context_clear("match")
        
        # ---------------------------------------------------------------------------------
        # AFTER TRANSITION
        
        if self.debug :
            print_ind( f"[>] State k  : {self.state}", 1)
        
        # If message is meant for the user eyes only then return
        if isinstance( message, ServerMsg) and message.user_eyes :
            return
        
        # Else append message to corresponding agent's context
        elif (
            (
                self.state in (
                    "idle",
                    "have_nothing",
                    "have_model_no_image",
                    "have_image_no_model",
                    "image_agent"
                )
            )
            and msg_has_image
        ) :
            self.agent_context_append( "image", message)
        
        elif self.state == "match_agent" :
            self.agent_context_append( "match", message)
        
        elif self.state == "main_agent" :
            self.agent_context_append( "main", message)
        
        return
    
    # =====================================================================================
    # DRONE MODEL SETUP
    # =====================================================================================
    
    def validate_model_choice(
        self,
        model_choice : str | None,
    ) -> str :
        
        if not model_choice :
            raise ValueError(
                f"In {here()}: Missing drone model choice"
            )
        
        if model_choice not in self.tool_server.dkdb.MODELS_AVAILABLE :
            raise ValueError(
                f"In {here()}: Invalid drone model choice '{model_choice}'"
            )
        
        return model_choice
    
    def ensure_model_loaded(self) -> None :
        
        model_choice = self.validate_model_choice(self.model_choice)
        
        if ( loaded_model := self.tool_server.dkdb.model ) :
            
            if loaded_model != model_choice :
                raise ValueError(
                    f"In {here()}: Loaded drone model '{loaded_model}' does not "
                    f"match selected model '{model_choice}'"
                )
            
            return
        
        error, result = self.tool_server.dkdb.set_model(model_choice)
        if error :
            raise ValueError(f"In {here()}: {result}")
        
        return
    
    # =====================================================================================
    # PROCESS MESSAGE FROM HUMAN
    # =====================================================================================
    
    async def process_message(
        self,
        message       : WhatsAppMessage,
        media_content : bytes | None = None,
    ) -> bool :
        
        # Dedup and ingest message
        msg = await self.dedup_and_ingest_message( message, media_content)
        if isinstance( msg, HumanServerMsg) :
            return False
        
        # If user message is not text, image, interactive reply then reply with a
        # message indicating lack of support
        if message.type not in ( "text", "image", "interactive") :
            
            system_message = self.load_system_message("unsupported.json")
            msg_reply      = ServerTextMsg(
                origin = here(),
                text   = system_message.get("body"),
            )
            msg_reply.print()
            
            # Write reply message to storage and update manifest
            msg_reply = await self.apply_and_persist_message(msg_reply)
            # Send reply message to user
            await self.send_text(msg_reply)
            
            # Signal need to wait for user's reply
            return False
        
        # Signal need to generate a response
        return True if msg else False
    
    # =====================================================================================
    # RUN WHILE_IN ACTION AS A FUNCTION OF FSM STATE
    # =====================================================================================
    
    async def run_while_in_action(
        self,
        max_tokens : int | None = None,
    ) -> bool :
        
        # If necessary then build context
        if not self.case_context :
            await self.context_build()
        
        # Retrieve manually-dispatched actions from current state
        state = self.machine.get_state(self.state)
        for action in state.while_in :
            
            if action == "ask_for_model_having_nothing" :
                return await self.ask_user_for("model_having_nothing")
            
            elif action == "ask_for_model_having_image" :
                return await self.ask_user_for("model_having_image")
            
            elif action == "ask_for_image" :
                return await self.ask_user_for("image")
            
            elif action == "call_image_agent" :
                return await self.call_image_agent(max_tokens)
            
            elif action == "call_match_agent" :
                return await self.call_match_agent(max_tokens)
            
            elif action == "call_main_agent" :
                return await self.call_main_agent(max_tokens)
        
        return False
    
    async def ask_user_for( self, argument : str) -> bool :
        
        origin = here()
        
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
            message = ServerInteractiveOptsMsg(
                origin  = origin,
                type    = "button",
                header  = msg_header,
                body    = msg_body,
                options = msg_options,
            )
            message.print()
            
            # Write message to storage and update manifest and state machine
            message = await self.apply_and_persist_message(message)
            # Send message to user
            await self.send_interactive(message)
        
        elif argument == "image" :
            
            system_message = self.load_system_message("ask_for_image.json")
            message        = ServerTextMsg(
                origin = origin,
                text   = system_message.get("body"),
            )
            message.print()
            
            # Write message to storage and update manifest and state machine
            message = await self.apply_and_persist_message(message)
            # Send message to user
            await self.send_text(message)
        
        else :
            raise ValueError(f"In {origin}: Invalid argument {argument}")
        
        # Return False because we need to wait for user to reply
        return False
    
    # =====================================================================================
    # SETUP AND CALL IMAGE ANALYSIS AGENT
    # =====================================================================================
    
    def setup_image_agent(self) -> None :
        
        self.ensure_model_loaded()
        self.image_agent = AsyncAgent( "image", self.IMAGE_AGENT_MODELS)
        
        drone_model = self.tool_server.dkdb.model
        prompt_path = self.PACKAGE_DIR / f"agent_prompts/image_{drone_model}.md"
        
        self.image_agent.load_prompts([prompt_path])
        
        return
    
    async def call_image_agent( self, max_tokens : int | None = None) -> bool :
        # ---------------------------------------------------------------------------------
        # Send agent update to user
        await self.send_agent_update("image_start")
        
        # ---------------------------------------------------------------------------------
        # Set text for message origin field
        origin = here()
        
        # If necessary then setup agent
        if not self.image_agent :
            self.setup_image_agent()
        
        # ---------------------------------------------------------------------------------
        # STAGE 1: GENERATE IMAGE ANALYSIS
        
        # Generate response
        message = await self.image_agent.get_response(
            context    = self.agent_contexts["image"],
            origin     = f"{origin}[stage-1]",
            load_imgs  = True,
            output_st  = RCImageAnalysis,
            max_tokens = max_tokens,
            debug      = self.debug,
        )
        
        # If the agent did not respond then simply return False
        if not message or message.is_empty() :
           return False
        else :
            message.print()
        
        # Write message to storage and update manifest and state machine
        await self.apply_and_persist_message(message)
        
        # ---------------------------------------------------------------------------------
        # STAGE 2: INJECT MESSAGE FOR MATCH AGENT
        
        # Retrive data from Domain Knowledge Database
        data_str = self.tool_server.dkdb.list_messages()
        # Construct message
        msg_with_data = ServerTextMsg( origin = f"{origin}[stage-2]",
                                       text   = data_str )
        msg_with_data.print()
        # Write message to storage and update manifest and state machine
        await self.apply_and_persist_message(msg_with_data)
        
        # ---------------------------------------------------------------------------------
        # Signal need for another response
        return True
    
    # =====================================================================================
    # SETUP AND CALL MATCH AGENT
    # =====================================================================================
    
    def setup_match_agent(self) -> None :
        
        self.ensure_model_loaded()
        self.match_agent = AsyncAgent( "match", self.MAIN_AGENT_MODELS)
        
        lan_reg_data = self.user_data.lan_reg_data if self.user_data else None
        country      = lan_reg_data.country  if lan_reg_data else None
        language     = lan_reg_data.language if lan_reg_data else None
        
        prompts_dir      = self.PACKAGE_DIR / "agent_prompts"
        match_ag_prompts = [
            {
                "path"    : prompts_dir / "match.md",
                "replace" : {},
            },
            {
                "path"    : prompts_dir / "user_profile.md",
                "replace" : {
                    "{COUNTRY}"  : country  or "Unknown",
                    "{LANGUAGE}" : language or "English",
                },
            },
            {
                "path"    : prompts_dir / "spanish.md",
                "replace" : {},
            },
        ]
        match_ag_tools   = [ self.PACKAGE_DIR / "agent_tools/match.json" ]
        
        self.match_agent.load_prompts(match_ag_prompts)
        self.match_agent.load_tools(match_ag_tools)
        self.match_agent.post_processors.append(markdown_to_whatsapp)
        
        return
    
    async def call_match_agent( self, max_tokens : int | None = None) -> bool :
        # ---------------------------------------------------------------------------------
        # Send agent update to user
        # self.send_agent_update( "match_start", debug)
        
        # ---------------------------------------------------------------------------------
        # Set text for message origin field
        origin = here()
        
        # If necessary then setup agent
        if not self.match_agent :
            self.setup_match_agent()
        
        # ---------------------------------------------------------------------------------
        # STAGE 1: GENERATE INITIAL MATCH AGENT RESPONSE
        
        # Generate response
        message = await self.match_agent.get_response(
            context    = self.agent_contexts["match"],
            origin     = f"{origin}[stage-1]",
            max_tokens = max_tokens,
            debug      = self.debug,
        )
        
        # If the agent did not respond then simply return False
        if not message or message.is_empty() :
           return False
        else :
            message.print()
        
        # Write message to storage and update manifest and state machine
        message = await self.apply_and_persist_message(message)
        
        # If message contains text then send it to the human user
        if message.text :
            await self.send_text(message)
        
        # If there are no tool calls then there is no need for more responses
        if not message.tool_calls :
            return False
        
        # ---------------------------------------------------------------------------------
        # STAGE 2: PROCESS TOOL CALLS, WRITE RESULTS TO CONTEXT, AND RETURN TRUE.
        
        tool_results = self.tool_server.process(message.tool_calls)
        if tool_results :
            # Construct message
            message = ToolResultsMsg(
                origin       = f"{origin}[stage-2]",
                tool_results = tool_results,
            )
            message.print()
            # Write message to storage and update manifest and state machine
            await self.apply_and_persist_message(message)
        
        # ---------------------------------------------------------------------------------
        # Signal need for another response
        return True
    
    # =====================================================================================
    # SETUP AND CALL MAIN AGENT
    # =====================================================================================
    
    def setup_main_agent(self) -> None :
        
        self.ensure_model_loaded()
        self.main_agent = AsyncAgent( "main", self.MAIN_AGENT_MODELS)
        
        lan_reg_data = self.user_data.lan_reg_data if self.user_data else None
        country      = lan_reg_data.country  if lan_reg_data else None
        language     = lan_reg_data.language if lan_reg_data else None
        
        prompts_dir     = self.PACKAGE_DIR / "agent_prompts"
        drone_model     = self.tool_server.dkdb.model
        main_ag_prompts = [
            {
                "path"    : prompts_dir / f"main_{drone_model}.md",
                "replace" : {},
            },
            {
                "path"    : prompts_dir / "user_profile.md",
                "replace" : {
                    "{COUNTRY}"  : country  or "Unknown",
                    "{LANGUAGE}" : language or "English",
                },
            },
            {
                "path"    : prompts_dir / "spanish.md",
                "replace" : {},
            }
        ]
        
        main_ag_tools = [ self.PACKAGE_DIR / "agent_tools/main.json" ]
        
        self.main_agent.load_prompts(main_ag_prompts)
        self.main_agent.load_tools(main_ag_tools)
        self.main_agent.post_processors.append(markdown_to_whatsapp)
        
        return
    
    async def call_main_agent( self, max_tokens : int | None = None) -> bool :
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
        origin = here()
        
        # ---------------------------------------------------------------------------------
        # STAGE 1: GENERATE INITIAL MAIN AGENT RESPONSE
        
        # If necessary then setup agent
        if not self.main_agent :
            self.setup_main_agent()
        
        # Generate main agent response
        message = await self.main_agent.get_response(
            context    = self.agent_contexts["main"],
            origin     = f"{origin}[stage-1]",
            max_tokens = max_tokens,
            debug      = self.debug,
        )
        
        # If the agent did not respond then simply return False
        if not message or message.is_empty() :
           return False
        else :
            message.print()
        
        # Write message to storage and update manifest and state machine
        message = await self.apply_and_persist_message(message)
        
        # Send message to user
        await self.send_text(message)
        
        # If there are no tool calls then there is no need for more responses
        if not message.tool_calls :
            return False
        
        # ---------------------------------------------------------------------------------
        # STAGE 2: PROCESS TOOL CALLS, WRITE RESULTS TO CONTEXT, AND RETURN TRUE.
        
        # Process high level tool calls
        for tc in message.tool_calls :
            if tc.name == "mark_as_resolved" :
                await self.case_mark_as_resolved()
        # Process low level tool calls
        tool_results = self.tool_server.process(message.tool_calls)
        
        # Process tool results
        if tool_results :
            # Construct message
            message = ToolResultsMsg(
                origin       = f"{origin}[stage-2]",
                tool_results = tool_results,
            )
            message.print()
            # Write message to storage and update manifest and state machine
            await self.apply_and_persist_message(message)
        
        # If case remains open then signal need for another response
        return bool( self.case_manifest and self.case_manifest.is_open )
    
    # =====================================================================================
    # OTHER HELPERS
    # =====================================================================================
    
    def load_system_message( self, json_file : str) -> dict[ str, str] :
        
        lan_reg_data  = (
            self.user_data.lan_reg_data
            if self.user_data else None
        )
        language_code = (
            lan_reg_data.code_lan
            if lan_reg_data else None
        )
        languate_dict : dict = load_json_file(
            self.PACKAGE_DIR / "agent_prompts" / json_file
        )
        
        return languate_dict.get(language_code) or languate_dict.get("en") or {}
    
    async def send_agent_update( self, message_name : str) -> None :
        
        # Fetch agent update messages
        agent_updates : dict = self.load_system_message("agent_updates.json")
        message_text  : str  = agent_updates.get(message_name)
        if message_text :
            # Construct message
            message = ServerTextMsg(
                origin    = here(),
                text      = message_text,
                user_eyes = True,
            )
            message.print()
            # Write message to storage and update manifest and state machine
            message = await self.apply_and_persist_message(message)
            # Send message to human
            await self.send_text(message)
        
        return
