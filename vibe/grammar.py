"""Formal grammar definition for Vibe Phase 1.1.

This PEG-like grammar is the canonical syntax source used by the parser.
"""

from __future__ import annotations

GRAMMAR = r"""
program         <- prelude* core_block+ experimental_block* EOF
prelude         <- vibe_version / import / module / type / enum / interface
vibe_version    <- 'vibe_version' WS VERSION NEWLINE
import          <- 'import' WS IDENT_PATH NEWLINE
module          <- 'module' WS IDENT_PATH NEWLINE
type            <- 'type' WS IDENT_PATH NEWLINE
enum            <- 'enum' WS IDENT_PATH NEWLINE
interface       <- 'interface' WS IDENT_PATH NEWLINE

core_block      <- intent_block / preserve_block / constraint_block / bridge_block / agent_block / orchestrate_block / emit_stmt
intent_block    <- 'intent' WS IDENT ':' NEWLINE INDENT intent_item+ DEDENT
intent_item     <- goal_item / io_block
io_block        <- ('inputs' / 'outputs') ':' NEWLINE INDENT field_decl+ DEDENT
field_decl      <- IDENT ':' WS? TYPE NEWLINE
goal_item       <- 'goal:' WS? STRING NEWLINE

preserve_block  <- 'preserve:' NEWLINE INDENT preserve_rule+ DEDENT
constraint_block<- 'constraint:' NEWLINE INDENT constraint_line+ DEDENT
bridge_block    <- 'bridge:' NEWLINE INDENT bridge_setting+ DEDENT
agent_block     <- 'agent' WS IDENT ':' NEWLINE INDENT agent_item+ DEDENT
agent_item      <- role_item / receives_item / emits_item / agent_preserve_item / agent_constraint_item
role_item       <- 'role:' WS? STRING NEWLINE
receives_item   <- 'receives:' WS? TYPE NEWLINE
emits_item      <- 'emits:' WS? TYPE NEWLINE
agent_preserve_item <- 'preserve:' WS? TYPE NEWLINE
agent_constraint_item <- 'constraint:' WS? TYPE NEWLINE
orchestrate_block <- 'orchestrate' WS IDENT ':' NEWLINE INDENT orchestrate_item+ DEDENT
orchestrate_item <- edge_line / on_error_line
edge_line       <- IDENT WS? '->' WS? IDENT NEWLINE
on_error_line   <- 'on_error:' WS? IDENT_PATH NEWLINE
emit_stmt       <- 'emit' WS IDENT NEWLINE?

experimental_block <- tesla_block / agentora_block / agentception_block

tesla_block     <- 'experimental.tesla.victory.layer' WS? '{' block_content '}'
agentora_block  <- 'agentora' WS? '{' block_content '}'
agentception_block <- 'agentception' WS? '{' block_content '}'
"""
