"""
CaseHandler State Machine

Uses the transitions library to implement a state machine for detecting
various triggers in the case context.
"""

from typing import Type

from transitions import ( Machine,
                          State)

from sofia_utils.printing import ( print_ind,
                                   print_sep )
from wa_agents.basemodels import ( AssistantMsg,
                                   Message,
                                   ServerMsg,
                                   UserMsg,
                                   UserInteractiveReplyMsg,
                                   UserContentMsg )


class StateMachine :
    """
    State Machine for detecting triggers in context
    """
    
    def __init__( self,
                  machine_cls : Type[Machine] = Machine,
                  **machine_kwargs
                ) -> None :
        """
        Initialize the State Machine
        """
        # Define states with on_enter and on_exit actions
        self.states = [
        
        # Information-gathering states
        State( "idle",                on_enter = [ "ask_for_model_having_nothing" ]),
        State( "have_model_no_image", on_enter = [ "ask_for_image", "set_model"   ]),
        State( "have_image_no_model", on_enter = [ "ask_for_model_having_image"   ]),
        
        # Single-task agents
        State( "image_agent", on_enter = [ "call_image_agent", "set_model" ],
                              on_exit  = [ "clear_image_agent_context" ]),
        State( "match_agent", on_enter = [ "call_match_agent" ],
                              on_exit  = [ "clear_match_agent_context" ]),
        
        # Main agent
        State( "main_agent", on_enter = [ "call_main_agent" ])
        
        ]
        
        # Initialize state machine
        self.machine = machine_cls( model   = self,
                                    states  = self.states,
                                    initial = 'idle',
                                    auto_transitions = False,
                                    **machine_kwargs )
        
        # Build state machine transitions
        self.build_transitions()
        
        # Build dummy methods for the on_enter actions
        self.actions : set[str] = set()
        for state in self.states :
            for action_ in state.on_enter :
                if action_ not in self.actions :
                    setattr( self, action_, lambda : None)
                    self.actions.add(action_)
        
        # Persistent variables and agent contexts
        self.model_choice = None
        self.image_agent_context : list[Message] = []
        self.match_agent_context : list[Message] = []
        self.main_agent_context  : list[Message] = []
        
        # Functions to clear contexts (for on_exit)
        self.clear_image_agent_context = lambda : self.image_agent_context.clear()
        self.clear_match_agent_context = lambda : self.match_agent_context.clear()
        
        # Initialize debug flag
        self.debug = False
        
        return
    
    def build_transitions(self) -> None :
        """
        Define all state transitions
        """
        # From state: idle
        self.machine.add_transition(
            source  = 'idle',
            trigger = 'has_model_choice',
            dest    = 'have_model_no_image'
        )
        self.machine.add_transition(
            source  = 'idle',
            trigger = 'has_image',
            dest    = 'have_image_no_model'
        )
        # From state: have_model_no_image
        self.machine.add_transition(
            source  = 'have_model_no_image',
            trigger = 'has_image',
            dest    = 'image_agent'
        )
        # From state: have_image_no_model
        self.machine.add_transition(
            source  = 'have_image_no_model',
            trigger = 'has_model_choice',
            dest    = 'image_agent'
        )
        # From state: image_agent
        self.machine.add_transition(
            source  = 'image_agent',
            trigger = 'has_image_analysis',
            dest    = 'match_agent'
        )
        # From state: match_agent
        self.machine.add_transition(
            source  = 'match_agent',
            trigger = 'has_match_tool_call',
            dest    = 'main_agent'
        )
        # From state: main_agent
        self.machine.add_transition(
            source  = 'main_agent',
            trigger = 'has_image',
            dest    = 'image_agent'
        )
        return
    
    def ingest_message( self, msg : Message) -> None :
        """
        Ingest a single message and execute corresponding state transition
        Args:
            msg: Message object to process
        """
        # ---------------------------------------------------------------------------------
        # BEFORE TRANSITION
        
        has_model_choice    = False
        has_image           = False
        has_image_analysis  = False
        has_match_tool_call = False
        
        if isinstance( msg, UserMsg) :
            # Flag model choice
            has_model_choice = isinstance( msg, UserInteractiveReplyMsg)
            if has_model_choice :
                self.model_choice = msg.choice.id
            # Flag image
            has_image = isinstance( msg, UserContentMsg) \
                        and msg.media and msg.media.mime.startswith("image")
        
        elif isinstance( msg, AssistantMsg) :
            # Flag image analysis
            has_image_analysis = ( msg.agent == "image" )
            # Flag match agent tool call
            has_match_tool_call = ( msg.agent == "match" ) and bool(msg.tool_calls)
        
        # ---------------------------------------------------------------------------------
        # TRANSITION
        
        match self.state :
            
            case 'idle' :
                if has_model_choice :
                    self.has_model_choice()
                elif has_image :
                    self.has_image()
            
            case 'have_model_no_image' :
                if has_image :
                    self.has_image()
            
            case 'have_image_no_model' :
                if has_model_choice :
                    self.has_model_choice()
            
            case 'image_agent' :
                if has_image_analysis :
                    self.has_image_analysis()
            
            case 'match_agent' :
                if has_match_tool_call :
                    self.has_match_tool_call()
            
            case 'main_agent' :
                if has_image :
                    self.has_image()
        
        # ---------------------------------------------------------------------------------
        # AFTER TRANSITION
        
        # If message is meant for the user eyes only then return
        if isinstance( msg, ServerMsg) and msg.user_eyes :
            return
        # Else append message to corresponding agent's context
        match self.state :
            case 'idle'|'have_model_no_image'|'have_image_no_model'|'image_agent' :
                if has_image :
                    self.image_agent_context.append(msg)
            case 'match_agent' :
                self.match_agent_context.append(msg)
            case 'main_agent' :
                self.main_agent_context.append(msg)
        
        return
    
    def evaluate_triggers_from_states(self) -> dict[ str, bool] :
        """
        Evaluate triggers from states
        Returns:
            Dictionary mapping trigger names to booleans
        """
        # Build dictionary mapping all state actions to booleans
        state   = self.machine.get_state(self.state)
        actions = getattr( state, 'on_enter', [])
        result  = { act : bool( act in actions ) for act in self.actions }
        
        return result
    
    def process( self, messages : list[Message]) -> dict[ str, bool] :
        """
        Process a list of messages and compute trigger states.
        Args:
            messages: List of Message objects to process
        Returns:
            Dictionary mapping trigger names to booleans
        """
        if self.debug :
            print_sep()
            print(f"{self.__class__.__name__} trace:")
        
        # Reset state machine
        self.state = 'idle'

        if self.debug :
            print_ind( f"[>] State: {self.state}", 1)
        
        # Process each message
        for msg in messages :
            self.ingest_message(msg)
            if self.debug :
                print_ind( f"[>] State: {self.state}", 1)
        
        return self.evaluate_triggers_from_states()
    
    def update( self, message : Message) -> dict[ str, bool] :
        """
        Process a single message and update trigger states.
        Args:
            message: Message object to process
        Returns:
            Dictionary mapping trigger names to booleans
        """
        if self.debug :
            print_sep()
            print(f"{self.__class__.__name__} trace:")
            print_ind( f"[>] State: {self.state}", 1)
        
        # Process single message
        self.ingest_message(message)
        
        if self.debug :
            print_ind( f"[>] State: {self.state}", 1)
        
        return self.evaluate_triggers_from_states()
