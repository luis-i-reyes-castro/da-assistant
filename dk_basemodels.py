"""
Domain Knowledge BaseModel Classes
"""

from decimal import Decimal
from pathlib import Path
from pydantic import ( BaseModel,
                       ConfigDict,
                       Field,
                       field_serializer )
from pydantic.type_adapter import TypeAdapter
from typing import ( Annotated,
                     Any,
                     Literal,
                     Type )

from caseflow_agents.basemodels import ( NN_Decimal,
                                         NE_dict_str,
                                         NE_list_str,
                                         NE_str )
from sofia_utilities.file_io import ( clean_filename,
                                      LoadMode,
                                      list_files_starting_with,
                                      load_file_as_string,
                                      strip_jsonc_comments )

# -----------------------------------------------------------------------------------------
# TYPES
# -----------------------------------------------------------------------------------------
type NoteData   = NE_str | NE_dict_str
type Graph_Edge = Annotated[ list[NE_str], Field( min_length = 2, max_length = 2) ]

class MoreInfo(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    components : list[NE_str] | None = None
    issues     : list[NE_str] | None = None
    signals    : list[NE_str] | None = None

# -----------------------------------------------------------------------------------------
# DKA (i.e., DK before parsing/expansion)
# -----------------------------------------------------------------------------------------

class DKA_Component(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    key           : NE_str | None = None # Set in DKDB's constructor
    type          : NE_str
    name          : NE_str
    name_alt      : NE_str | list[NE_str] | None = None
    name_spanish  : NE_str | list[NE_str] | None = None
    material_num  : NE_str
    material_name : NE_str
    risk          : NN_Decimal
    notes         : list[NoteData] | None = None
    connected_to  : list[NE_str]   | None = None
    
    @field_serializer( 'risk', mode = 'plain')
    def serialize_risk( self, risk : Decimal) :
        return float(risk)

class DKA_Connections(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    sides   : list[NE_str]
    bridges : dict[ NE_str, Annotated[ list[Graph_Edge], Field( min_length = 1)]]
    edges   : dict[ NE_str, Annotated[ list[Graph_Edge], Field( min_length = 1)]]

class DKA_Issue(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    key       : NE_str | None = None # Set in DKDB's constructor
    name      : NE_str
    notes     : list[NoteData] | None = None
    solutions : list[NoteData]

class DKA_SignalPath(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    comp_A : NE_str
    comp_B : NE_str
    bridge : NE_str | None = None

class DKA_SignalGroup(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    signals : NE_list_str
    path    : DKA_SignalPath

class DKA_MessageKey(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    key          : NE_str
    name         : NE_str
    name_spanish : NE_str | list[NE_str] | None = None
    notes        : list[NoteData]        | None = None

class DKA_MessageCauses(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    issues  : list[NE_str] | None = None
    signals : list[NE_str] | None = None

class DKA_MessageGroup(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    messages     : Annotated[ list[DKA_MessageKey], Field( min_length = 1)]
    causes       : DKA_MessageCauses | None = None
    disaggregate : list[NE_str]      | None = None
    notes        : list[NoteData]    | None = None
    more_info    : MoreInfo          | None = None

type DKA_Components_File = dict[ NE_str, DKA_Component ]
type DKA_Issues_File     = dict[ NE_str, DKA_Issue ]
type DKA_Signals_File    = list[ DKA_SignalGroup ]
type DKA_Messages_File   = list[ DKA_MessageGroup ]

# -----------------------------------------------------------------------------------------
# DKB (i.e., DK after parsing/expansion)
# -----------------------------------------------------------------------------------------

DKB_Component   = DKA_Component
DKB_Connections = DKA_Connections
DKB_Issue       = DKA_Issue

class DKB_SignalEntry(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    key   : NE_str | None = None # Set in DKDB's constructor
    path  : DKA_SignalPath
    path_ : NE_list_str
    notes : list[NoteData] | None = None

class DKB_MessageEntry(BaseModel) :
    
    model_config = ConfigDict( extra = "forbid" )
    
    key          : NE_str | None = None
    name         : NE_str
    name_spanish : NE_str | list[NE_str] | None = None
    causes       : DKA_MessageCauses     | None = None
    disaggregate : list[NE_str]          | None = Field( serialization_alias =
                                                         "disaggregated_into_messages",
                                                         default             = None )
    
    notes        : list[NoteData] | None = None
    more_info    : MoreInfo       | None = None

DKB_Components_File = dict[ NE_str, DKB_Component ]
DKB_Issues_File     = dict[ NE_str, DKB_Issue ]
DKB_Signals_File    = dict[ NE_str, DKB_SignalEntry ]
DKB_Messages_File   = dict[ NE_str, DKB_MessageEntry ]

# -----------------------------------------------------------------------------------------
# DK Loaders
# -----------------------------------------------------------------------------------------

def load_dk_data( data_type : Type,
                  filenames : list[ str | Path ],
                  mode      : LoadMode ) -> dict[ str, Any] :
    
    type_adapter = TypeAdapter(data_type)
    result       = {}
    
    for filename_ in filenames :
        
        data_str = load_file_as_string(filename_)
        if Path(filename_).suffix.lower() == ".jsonc" :
            data_str = strip_jsonc_comments(data_str)
        
        match mode :
            case LoadMode.GROUP :
                clean_fn         = clean_filename(filename_)
                result[clean_fn] = type_adapter.validate_json(data_str)
            case LoadMode.MERGE :
                result.update( type_adapter.validate_json(data_str) )
    
    return result

def load_dka_components( dir_path  : str | Path) -> dict[ str, DKA_Components_File] :
    filenames = list_files_starting_with( dir_path, "components", "json")
    return load_dk_data( DKA_Components_File, filenames, LoadMode.GROUP)

def load_dka_issues( dir_path  : str | Path) -> dict[ str, DKA_Issues_File] :
    filenames = list_files_starting_with( dir_path, "issues", "json")
    return load_dk_data( DKA_Issues_File, filenames, LoadMode.GROUP)

def load_dka_signals( dir_path  : str | Path) -> dict[ str, DKA_Signals_File] :
    filenames = list_files_starting_with( dir_path, "signals", "json")
    return load_dk_data( DKA_Signals_File, filenames, LoadMode.GROUP)

def load_dka_messages( dir_path  : str | Path) -> dict[ str, DKA_Messages_File] :
    filenames = list_files_starting_with( dir_path, "messages", "json")
    return load_dk_data( DKA_Messages_File, filenames, LoadMode.GROUP)

def load_dkb_components( dir_path  : str | Path) -> DKB_Components_File :
    filenames = list_files_starting_with( dir_path, "components", "json")
    return load_dk_data( DKB_Components_File, filenames, LoadMode.MERGE)

def load_dkb_issues( dir_path  : str | Path) -> DKB_Issues_File :
    filenames = list_files_starting_with( dir_path, "issues", "json")
    return load_dk_data( DKB_Issues_File, filenames, LoadMode.MERGE)

def load_dkb_signals( dir_path  : str | Path) -> DKB_Signals_File :
    filenames = list_files_starting_with( dir_path, "signals", "json")
    return load_dk_data( DKB_Signals_File, filenames, LoadMode.MERGE)

def load_dkb_messages( dir_path  : str | Path) -> DKB_Messages_File :
    filenames = list_files_starting_with( dir_path, "messages", "json")
    return load_dk_data( DKB_Messages_File, filenames, LoadMode.MERGE)

# -----------------------------------------------------------------------------------------
# DK Database
# -----------------------------------------------------------------------------------------

class RCImageAnalysis(BaseModel) :
    """
    Remote Control Image Analysis
    """
    is_screen_photo : bool
    screen_type     : Literal[ "MOS", "HMS", "Other"] | None
    language        : str | None
    error_messages  : list[str]

class JD_Message(DKB_MessageEntry) :
    
    ignore : bool = Field( serialization_alias = "ignored", default = False)

class JD_Component(DKB_Component) :
    
    errors : list[NE_str] = Field( serialization_alias = "errors_triggered_when_faulty",
                                   default_factory     = list )

class JD_Issue(DKB_Issue) :
    
    errors : list[NE_str] = Field( serialization_alias = "errors_triggered_when_present",
                                   default_factory     = list )

class JointDiagnosis(BaseModel) :
    
    messages   : list[ JD_Message ]   = Field( default_factory = list )
    components : list[ JD_Component ] = Field( serialization_alias =
                                               "suggested_component_inspection_order",
                                               default_factory     = list )
    issues     : list[ JD_Issue ]     = Field( serialization_alias =
                                               "suggested_issue_inspection_order",
                                               default_factory     = list )
