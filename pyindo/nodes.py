from dataclasses import dataclass, field

from pyindo.diagnostics import SourceSpan


@dataclass(frozen=True)
class TypeAnnotation:
  name: str
  arguments: list["TypeAnnotation"]
  span: SourceSpan


@dataclass(frozen=True)
class Literal:
  value: int | float | str | bool | None
  span: SourceSpan


@dataclass(frozen=True)
class Name:
  identifier: str
  span: SourceSpan


@dataclass(frozen=True)
class ModuleMember:
  namespace: str
  member: str
  span: SourceSpan


@dataclass(frozen=True)
class Unary:
  operator: str
  operand: "Expression"
  span: SourceSpan


@dataclass(frozen=True)
class Binary:
  operator: str
  left: "Expression"
  right: "Expression"
  span: SourceSpan


@dataclass(frozen=True)
class Logical:
  operator: str
  left: "Expression"
  right: "Expression"
  span: SourceSpan


@dataclass(frozen=True)
class Conditional:
  true_value: "Expression"
  condition: "Expression"
  false_value: "Expression"
  span: SourceSpan


@dataclass(frozen=True)
class ListLiteral:
  items: list["Expression"]
  span: SourceSpan


@dataclass(frozen=True)
class Index:
  container: "Expression"
  index: "Expression"
  span: SourceSpan


@dataclass(frozen=True)
class NonEmpty:
  operand: "Expression"
  span: SourceSpan


@dataclass(frozen=True)
class Call:
  callee: str
  arguments: list["Expression"]
  span: SourceSpan


@dataclass(frozen=True)
class InterpolatedString:
  parts: list["str | Expression"]
  span: SourceSpan


type Expression = (
  Literal | Name | ModuleMember | Unary | Binary | Logical | Conditional | ListLiteral | Index | NonEmpty | Call | InterpolatedString
)


@dataclass(frozen=True)
class Declaration:
  name: str
  value: Expression
  is_constant: bool
  span: SourceSpan
  annotation: TypeAnnotation | None = None


@dataclass(frozen=True)
class Assignment:
  target: str
  value: Expression
  span: SourceSpan


@dataclass(frozen=True)
class AugmentedAssignment:
  target: str
  operator: str
  value: Expression
  span: SourceSpan


@dataclass(frozen=True)
class IndexedAssignment:
  target: Index
  value: Expression
  span: SourceSpan


@dataclass(frozen=True)
class Delete:
  target: Index
  span: SourceSpan


@dataclass(frozen=True)
class Return:
  value: Expression | None
  span: SourceSpan


@dataclass(frozen=True)
class CallStatement:
  call: Call
  span: SourceSpan


@dataclass(frozen=True)
class If:
  branches: list[tuple[Expression, list["Statement"]]]
  else_body: list["Statement"] | None
  span: SourceSpan


@dataclass(frozen=True)
class While:
  condition: Expression
  body: list["Statement"]
  span: SourceSpan


@dataclass(frozen=True)
class For:
  initializer: "Statement | None"
  condition: Expression | None
  update: "Statement | None"
  body: list["Statement"]
  span: SourceSpan


@dataclass(frozen=True)
class ForEach:
  name: str
  annotation: TypeAnnotation | None
  is_constant: bool
  iterable: Expression
  body: list["Statement"]
  span: SourceSpan
  binding_span: SourceSpan


@dataclass(frozen=True)
class Break:
  span: SourceSpan


@dataclass(frozen=True)
class Continue:
  span: SourceSpan


type Statement = (
  Declaration | Assignment | AugmentedAssignment | IndexedAssignment | Delete | Return | CallStatement
  | If | While | For | ForEach | Break | Continue
)


@dataclass(frozen=True)
class Parameter:
  name: str
  span: SourceSpan
  annotation: TypeAnnotation | None = None


@dataclass(frozen=True)
class Function:
  name: str
  parameters: list[Parameter]
  body: list[Statement]
  span: SourceSpan
  name_span: SourceSpan | None = None
  return_annotation: TypeAnnotation | None = None


@dataclass(frozen=True)
class ImportBinding:
  name: str
  alias: str
  span: SourceSpan


@dataclass(frozen=True)
class Import:
  path: str
  bindings: list[ImportBinding]
  namespace: str | None
  span: SourceSpan
  path_span: SourceSpan


@dataclass(frozen=True)
class Program:
  functions: list[Function]
  source_text: str
  span: SourceSpan
  imports: list[Import] = field(default_factory=list)
  declarations: list[Declaration] = field(default_factory=list)
