"""
CaseHandler State Machine

Uses the transitions library to implement a state machine for detecting
various triggers in the case context.
"""

from transitions import ( Machine,
                          State)
from typing import Type

from sofia_utils.printing import ( print_ind,
                                   print_sep )
from wa_agents.basemodels import ( AssistantMsg,
                                   Message,
                                   ServerMsg,
                                   UserMsg,
                                   UserInteractiveReplyMsg,
                                   UserContentMsg )
from wa_agents.state_machine_base import StateMachineBase


class StateMachine(StateMachineBase) :
    """
    State Machine for detecting triggers in context
    """
    
    def __init__( self,
                  debug       : bool          = False,
                  machine_cls : Type[Machine] = Machine,
                  **machine_kwargs
                ) -> None :
        """
        Initialize the State Machine
        """
        super().__init__(debug)
        
        # Define states with on_enter and on_exit actions
        self.states = [
        
        # Information-gathering states
        State( "idle",                on_enter = [ "ask_for_model_having_nothing" ]),
        State( "have_model_no_image", on_enter = [ "set_model",
                                                   "ask_for_image"                ]),
        State( "have_image_no_model", on_enter = [ "ask_for_model_having_image"   ]),
        
        # Single-task agents
        State( "image_agent", on_enter = [ "set_model",
                                           "call_image_agent"          ],
                              on_exit  = [ "clear_image_agent_context" ]),
        State( "match_agent", on_enter = [ "call_match_agent"          ],
                              on_exit  = [ "clear_match_agent_context" ]),
        
        # Main agent
        State( "main_agent", on_enter = [ "call_main_agent" ])
        
        ]
        
        # Define transitions
        self.transitions = [
        
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
        
        # Initialize state machine
        self.machine = machine_cls( model   = self,
                                    states  = self.states,
                                    initial = "idle",
                                    transitions      = self.transitions,
                                    auto_transitions = False,
                                    ignore_invalid_triggers = True,
                                    **machine_kwargs )
        
        # Persistent variables and agent contexts
        self.model_choice        : str           = None
        self.image_agent_context : list[Message] = []
        self.match_agent_context : list[Message] = []
        self.main_agent_context  : list[Message] = []
        
        # Functions to clear contexts (for on_exit)
        self.clear_image_agent_context = lambda : self.image_agent_context.clear()
        self.clear_match_agent_context = lambda : self.match_agent_context.clear()
        
        # Build dummy methods
        self.build_dummy_methods_for_on_enter_and_on_exit()
        
        return
    
    def ingest_message( self, message : Type[Message]) -> None :
        """
        Ingest a single message and fire corresponding triggers\n
        Args:
            message: Instance of a subclass of Message
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
