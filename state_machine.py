"""
CaseHandler State Machine

Uses the transitions library to implement a state machine for detecting
various triggers in the case context.
"""

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


class StateWithColor(State) :
    """
    State with color (for drawing state machine graph)
    """
    def __init__( self,
                  name     : str,
                  color    : str = "white",
                  on_enter : list[str] | None = None ) -> None :
        
        super().__init__( name, on_enter)
        self.color = color
        
        return

class StateMachine :
    """
    State Machine for detecting triggers in context
    """
    
    def __init__( self,
                  machine_cls : type[Machine] = Machine,
                  **machine_kwargs
                ) -> None :
        """
        Initialize the FSM with states and transitions
        """
        # Define states with actions for diagram display
        self.states = [
        
        StateWithColor( "idle", "white",
                        [ "ask_for_model_having_nothing" ] ),
        
        StateWithColor( "have_model_no_image", "white",
                        [ "set_model",
                          "ask_for_image" ]                ),
        
        StateWithColor( "have_image_no_model", "white",
                        [ "ask_for_model_having_image" ]   ),
        
        StateWithColor( "image_agent", "orange",
                        [ "set_model",
                          "call_image_agent" ] ),
        
        StateWithColor( "match_agent", "orange",
                        [ "call_match_agent" ] ),
        
        StateWithColor( "main_agent",  "orange",
                        [ "call_main_agent" ]  )
        
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
        
        # Persistent variables
        self.model_choice = None
        self.msgs_for_image_agent : list[Message] = []
        self.msgs_for_match_agent : list[Message] = []
        self.msgs_for_main_agent  : list[Message] = []
        
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
        prev_state          = self.state
        
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
        
        # Single-task agents: Clear context when leaving their states
        if self.state != prev_state :
            if prev_state == 'image_agent' :
                self.msgs_for_image_agent.clear()
            elif prev_state == 'match_agent' :
                self.msgs_for_match_agent.clear()
        
        # If message is meant for the user eyes only then return
        if isinstance( msg, ServerMsg) and msg.user_eyes :
            return
        # Else append message to corresponding agent's context
        match self.state :
            case 'idle'|'have_model_no_image'|'have_image_no_model'|'image_agent' :
                if has_image :
                    self.msgs_for_image_agent.append(msg)
            case 'match_agent' :
                self.msgs_for_match_agent.append(msg)
            case 'main_agent' :
                self.msgs_for_main_agent.append(msg)
        
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
    
    def process( self,
                 messages : list[Message],
                 debug    : bool = False
               ) -> dict[ str, bool] :
        """
        Process a list of messages and compute trigger states.
        Args:
            messages: List of Message objects to process
            debug:    Debug mode flag
        Returns:
            Dictionary mapping triggers to booleans and persistent variables to their appropriate values.
        """
        if debug :
            print_sep()
            print(f"{self.__class__.__name__} trace:")
        
        # Reset state machine
        self.state = 'idle'

        if debug :
            print_ind( f"[>] State: {self.state}", 1)
        
        # Process each message
        for msg in messages :
            self.ingest_message(msg)
            if debug :
                print_ind( f"[>] State: {self.state}", 1)
        
        return self.evaluate_triggers_from_states()
    
    def update( self,
                message : Message,
                debug   : bool = False
              ) -> dict[ str, bool] :
        """
        Process a single message and update trigger states.
        Args:
            message: Message object to process
            debug:   Debug mode flag
        Returns:
            Dictionary mapping triggers to booleans and persistent variables to their appropriate values.
        """
        if debug :
            print_sep()
            print(f"{self.__class__.__name__} trace:")
            print_ind( f"[>] State: {self.state}", 1)
        
        # Process single message
        self.ingest_message(message)
        
        if debug :
            print_ind( f"[>] State: {self.state}", 1)
        
        return self.evaluate_triggers_from_states()
