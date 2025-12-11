# Allowable characters
RX_CHAR = r'([A-Z][A-Z0-9_]*)'
# Set signatures, function arguments and function signatures
RX_SET = fr'{{{RX_CHAR}}}'
RX_ARG = fr'\[{RX_CHAR}\]'
RX_FUN = fr'{{{RX_CHAR}{RX_ARG}}}'
# Acronyms to ignore
IGNORE = [ 'GNSS', 'IMU', 'FCC' ]
