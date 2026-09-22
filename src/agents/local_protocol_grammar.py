"""Canonical llama.cpp grammar for the local Home Assistant protocol."""

LOCAL_HOMEASSISTANT_GRAMMAR = r'''root ::= "```homeassistant" "\n" ws "{" ws "\"tool\"" ws ":" ws "\"control_smart_device\"" ws "," ws "\"arguments\"" ws ":" ws arguments ws "}" ws "\n" "```"
arguments ::= "{" ws "\"device_id\"" ws ":" ws string ws "," ws "\"action\"" ws ":" ws string ws "," ws "\"value\"" ws ":" ws value ws "}"
value ::= "null" | object | array | string | number | boolean
object ::= "{" ws (string ws ":" ws value (ws "," ws string ws ":" ws value)*)? ws "}"
array ::= "[" ws (value (ws "," ws value)*)? ws "]"
string ::= "\"" chars "\""
chars ::= ([^"\\] | "\\" ["\\/bfnrt] | "\\u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])*
number ::= "-"? [0-9]+ ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
boolean ::= "true" | "false"
ws ::= [ \t\n]*
'''

# This restricts only the fenced generic envelope. The runtime parser remains
# responsible for tool names and Pydantic argument-schema validation.
LOCAL_TOOL_CALLS_GRAMMAR = r'''root ::= "```tool_calls" "\n" ws "{" ws "\"calls\"" ws ":" ws "[" ws calls ws "]" ws "}" ws "\n" "```"
calls ::= call | call ws "," ws call | call ws "," ws call ws "," ws call | call ws "," ws call ws "," ws call ws "," ws call | call ws "," ws call ws "," ws call ws "," ws call ws "," ws call
call ::= "{" ws "\"name\"" ws ":" ws string ws "," ws "\"args\"" ws ":" ws object ws "}"
object ::= "{" ws (string ws ":" ws value (ws "," ws string ws ":" ws value)*)? ws "}"
array ::= "[" ws (value (ws "," ws value)*)? ws "]"
value ::= object | array | string | number | boolean | "null"
string ::= "\"" chars "\""
chars ::= ([^"\\] | "\\" ["\\/bfnrt] | "\\u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])*
number ::= "-"? [0-9]+ ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
boolean ::= "true" | "false"
ws ::= [ \t\n]*
'''
