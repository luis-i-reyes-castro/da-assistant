"""
CaseHander Tool Server
"""

from caseflow_agents.basemodels import ( ToolCall,
                                         ToolResult )
from dk_database import DomainKnowledgeDataBase

class ToolServer :
    
    def __init__(self) -> None :
        
        self.dkdb  = DomainKnowledgeDataBase()
        self.tools = [ "dummy_tool",
                       "get_component_data",
                       "get_joint_diagnosis",
                       "mark_as_resolved" ]
        
        return
    
    def process( self, tool_calls : list[ToolCall]) -> list[ToolResult] :
        
        tool_results = []
        
        for tc in tool_calls :
            matched_tool = self.dkdb.get_match( tc.name, self.tools)
            error  = True
            result = None
            e_msg  = None
            
            match matched_tool :

                case "dummy_tool" :
                    error, result = False, "Executed successfully"
                
                case "get_component_data" :
                    component_keys = tc.input.get("component_keys")
                    if component_keys :
                        error, result = self.dkdb.get_components(component_keys)
                    else :
                        e_msg = f"Tool 'get_component_data' called without 'component_keys'"
                
                case "get_joint_diagnosis" :
                    message_codes = tc.input.get("message_codes")
                    if message_codes :
                        error, result = self.dkdb.get_joint_diagnosis(message_codes)
                    else :
                        e_msg = f"Tool 'get_joint_diagnosis' called without 'message_codes'"
                
                case "mark_as_resolved" :
                    error, result = False, "Successfully marked case as resolved."
                
                case _ :
                    e_msg = f"Tool name '{tc.name}' could not be matched"
            
            if error and e_msg :
                result = f"In class AgentToolServer method process: {e_msg}"
            
            tr = ToolResult( id = tc.id, error = error, content = result)
            tool_results.append(tr)
        
        return tool_results
