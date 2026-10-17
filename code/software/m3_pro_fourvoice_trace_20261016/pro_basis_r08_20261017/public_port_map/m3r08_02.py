"""Lexical ANSI public-port checks. Expressions outside the subset stay unresolved."""
import ast
import importlib.util
from pathlib import Path
import re
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules[_s.name] = _m
    _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]


def clean(text):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def balanced(text, start):
    c.need(text[start] == "(", "PAREN_EXPECTED")
    depth, quoted, escape = 0, False, False
    for i in range(start, len(text)):
        char = text[i]
        if quoted:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise c.CheckError("UNBALANCED_HEADER")


def split_commas(text):
    depth, quoted, start, parts = 0, False, 0, []
    for i, ch in enumerate(text):
        if ch == '"' and (i == 0 or text[i - 1] != "\\"):
            quoted = not quoted
        if quoted:
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return parts


def number(expression, env):
    try:
        node = ast.parse(expression.strip(), mode="eval").body
        def walk(n):
            if isinstance(n, ast.Constant) and type(n.value) is int:
                return n.value
            if isinstance(n, ast.Name) and type(env.get(n.id)) is int:
                return env[n.id]
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
                return -walk(n.operand) if isinstance(n.op, ast.USub) else walk(n.operand)
            if isinstance(n, ast.BinOp):
                a, b = walk(n.left), walk(n.right)
                if isinstance(n.op, ast.Add): return a + b
                if isinstance(n.op, ast.Sub): return a - b
                if isinstance(n.op, ast.Mult): return a * b
                if isinstance(n.op, (ast.Div, ast.FloorDiv)) and b and a % b == 0: return a // b
                if isinstance(n.op, ast.LShift) and 0 <= b <= 64: return a << b
                if isinstance(n.op, ast.RShift) and 0 <= b <= 64: return a >> b
            raise ValueError("UNRESOLVED")
        return walk(node)
    except (ValueError, SyntaxError, RecursionError, OverflowError):
        return None


def width(raw, env):
    if not raw:
        return 1
    fields = raw.strip("[] ").split(":")
    if len(fields) != 2:
        return None
    a, b = (number(x, env) for x in fields)
    return abs(a - b) + 1 if a is not None and b is not None else None


def parameter_value(expression, env):
    expression = expression.strip()
    if re.fullmatch(r'"(?:[^"\\]|\\.)*"', expression):
        return ast.literal_eval(expression)
    if expression in env:
        return env[expression]
    return number(expression, env)


def parameters(text):
    expressions, values = {}, {}
    for token in split_commas(text):
        match = re.search(r"\b(\w+)\s*=\s*(.+)$", token, re.S)
        if match:
            key, expression = match.group(1), match.group(2).strip()
            expressions[key] = expression
            values[key] = parameter_value(expression, values)
    return expressions, values


def declarations(text, origin):
    output = {}
    for match in re.finditer(r"\bmodule\s+(\w+)\s*", text):
        name, i, parameter_text = match.group(1), match.end(), ""
        if i < len(text) and text[i] == "#":
            i += 1
            while text[i].isspace(): i += 1
            parameter_text, i = balanced(text, i)
        while i < len(text) and text[i].isspace(): i += 1
        if i >= len(text) or text[i] != "(":
            continue
        header, _ = balanced(text, i)
        params, env = parameters(parameter_text)
        ports, direction, signed, bus = {}, None, False, None
        for token in split_commas(header):
            pm = re.match(r"(input|output|inout)\b\s*(.*)", token, re.S)
            if pm:
                direction, token = pm.groups()
                signed, bus = False, None
            token = re.sub(r"\b(?:wire|logic|reg)\b", "", token).strip()
            if token.startswith("signed"):
                signed, token = True, token[6:].strip()
            bm = re.match(r"(\[[^\]]+\])\s*(.*)", token, re.S)
            if bm:
                bus, token = bm.groups()
            nm = re.match(r"(\w+)\s*(?:=\s*(.*))?$", token, re.S)
            if not nm or direction is None:
                continue
            ports[nm.group(1)] = {"direction": direction, "width": width(bus, env), "signed": signed,
                                  "width_expression": bus or "1", "source": origin,
                                  "declared_default": nm.group(2).strip() if nm.group(2) is not None else None}
        output[name] = {"ports": ports, "parameters": params, "parameter_values": env, "source": origin}
    return output


def named(text):
    result = {}
    for token in split_commas(text):
        pm = re.match(r"\.(\w+)\s*\(", token)
        c.need(pm is not None, "NAMED_CONNECTION_REQUIRED")
        value, end = balanced(token, pm.end() - 1)
        c.need(not token[end:].strip() and pm.group(1) not in result, "DUPLICATE_OR_BAD_CONNECTION")
        result[pm.group(1)] = value.strip()
    return result


def expression_width(expr, nets, env):
    if expr in nets:
        return nets[expr]
    literal = re.fullmatch(r"(\d+)'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ]+", expr)
    if literal:
        return int(literal.group(1))
    bit = re.fullmatch(r"(\w+)\[([^\]]+)\]", expr)
    if bit and bit.group(1) in nets:
        return width("[" + bit.group(2) + "]", env) if ":" in bit.group(2) else 1
    if "&&" in expr or "||" in expr or expr.startswith("!"):
        return 1 if all(n in nets for n in re.findall(r"[A-Za-z_]\w*", expr)) else None
    if expr.startswith("{") and expr.endswith("}"):
        parts = [expression_width(t, nets, env) for t in split_commas(expr[1:-1])]
        return sum(parts) if all(p is not None for p in parts) else None
    return None


def evaluate(request):
    c.need(request.get("schema") == "M3_R08_PORT_MAP_REQUEST_V1", "PORT_MAP_SCHEMA")
    catalog, ids = {}, []
    for entry in request["module_files"]:
        path, ident = c.checked_file(entry)
        for name, info in declarations(clean(path.read_text(encoding="utf-8")), ident["path"]).items():
            c.need(name not in catalog, "DUPLICATE_MODULE:" + name)
            catalog[name] = info
        ids.append(ident)
    for name in request["required_modules"]:
        c.need(name in catalog, "MISSING_WRAPPER_OR_MODULE:" + name)
    for rule in request["direction_rules"]:
        info = catalog[rule["module"]]["ports"].get(rule["port"])
        c.need(info is not None and info["direction"] == rule["direction"], "PUBLIC_DIRECTION_MISMATCH")
    top, top_id = c.checked_file(request["top_file"])
    text = clean(top.read_text(encoding="utf-8"))
    caller_env, caller_expressions = {}, {}
    header = re.search(r"\bmodule\s+\w+\s*#\s*\(", text)
    if header:
        caller_text, _ = balanced(text, header.end() - 1)
        caller_expressions, caller_env = parameters(caller_text)
    nets = {}
    for match in re.finditer(r"\b(?:wire|logic|reg)\s+(?:signed\s+)?(\[[^\]]+\])?\s*([^;]+);", text):
        for token in split_commas(match.group(2)):
            nm = re.match(r"(\w+)(?:\s*=.*)?$", token, re.S)
            if nm:
                nets[nm.group(1)] = width(match.group(1), caller_env)
    connections, drivers, unresolved, instances, instance_parameters = [], {}, [], set(), []
    for module, definition in catalog.items():
        for match in re.finditer(r"\b" + re.escape(module) + r"\b\s*", text):
            i, overrides = match.end(), {}
            if i < len(text) and text[i] == "#":
                i += 1
                while text[i].isspace(): i += 1
                args, i = balanced(text, i)
                overrides = named(args)
            instance = re.match(r"\s*(\w+)\s*\(", text[i:])
            if not instance:
                continue
            instance_name = instance.group(1)
            body, _ = balanced(text, i + instance.end() - 1)
            instances.add(module)
            c.need(set(overrides) <= set(definition["parameters"]), "UNKNOWN_PARAMETER_OVERRIDE")
            env = {}
            for key, default in definition["parameters"].items():
                expression = overrides.get(key, default)
                env[key] = parameter_value(expression, caller_env if key in overrides else env)
                if env[key] is None:
                    unresolved.append({"instance": instance_name, "parameter": key,
                                       "expression": expression, "reason": "UNRESOLVED_PARAMETER_IN_CALLER_SCOPE"})
            instance_parameters.append({"module": module, "instance": instance_name,
                                        "overrides": overrides, "numeric_values": env})
            connected = named(body)
            for port, declaration in definition["ports"].items():
                if declaration["direction"] == "input" and port not in connected:
                    c.need(declaration["declared_default"] is not None, "MISSING_REQUIRED_INPUT:" + port)
                    default_width = expression_width(declaration["declared_default"], nets, env)
                    if default_width is None or declaration["width"] is None:
                        unresolved.append({"instance": instance_name, "port": port,
                                           "expression": declaration["declared_default"], "reason": "UNRESOLVED_DECLARED_DEFAULT"})
                    else:
                        c.need(default_width == declaration["width"], "DEFAULT_WIDTH_UNRESOLVED:" + port)
            for port, expr in connected.items():
                c.need(port in definition["ports"], "UNKNOWN_PUBLIC_PORT:" + port)
                p = dict(definition["ports"][port])
                p["width"] = width(p["width_expression"], env) if p["width_expression"] != "1" else 1
                c.need(not re.search(r"\b[A-Za-z_]\w*\s*\.", expr), "PRIVATE_HIERARCHY")
                c.need(expr or p["direction"] == "output", "INPUT_LEFT_OPEN")
                actual = expression_width(expr, nets, env) if expr else p["width"]
                if p["width"] is not None and actual is not None:
                    c.need(actual == p["width"], "PUBLIC_WIDTH_MISMATCH:" + port)
                else:
                    unresolved.append({"instance": instance_name, "port": port, "expression": expr, "reason": "UNRESOLVED_WIDTH"})
                if p["direction"] == "output" and expr:
                    if re.fullmatch(r"[A-Za-z_]\w*", expr):
                        c.need(expr in nets, "OUTPUT_NOT_DECLARED_NET:" + port)
                        drivers.setdefault(expr, []).append(instance_name + "." + port)
                    elif re.fullmatch(r"[A-Za-z_]\w*\[[^\]]+\]", expr):
                        unresolved.append({"instance": instance_name, "port": port, "expression": expr,
                                           "reason": "UNRESOLVED_OUTPUT_DRIVER_RANGE"})
                    else:
                        raise c.CheckError("OUTPUT_EXPRESSION_NOT_WRITABLE:" + port)
                connections.append({"module": module, "instance": instance_name, "port": port,
                                    "expression": expr, "declared": p, "expression_width": actual})
    for name in request["required_modules"]:
        c.need(name in instances, "WRAPPER_NOT_INSTANTIATED:" + name)
    for net, sources in drivers.items():
        c.need(len(sources) == 1, "MULTIPLE_PUBLIC_DRIVERS:" + net)
    report = {"modules": catalog, "connections": connections, "drivers": drivers,
              "caller_parameter_expressions": caller_expressions, "caller_parameter_values": caller_env,
              "parameter_scope": "TOP_SOURCE_DEFAULTS_ONLY_NO_ELABORATION_OR_TOOL_OVERRIDES",
              "instance_parameters": instance_parameters,
              "unresolved": unresolved, "top": top_id, "source_identities": ids}
    return c.result("M3_R08_PUBLIC_PORT_MAP_V1", "PENDING_UNKNOWN" if unresolved else "ACCEPT",
                    report=report, compile_proven=False,
                    artifacts={"module_ports.json": catalog, "connections.json": report})


if __name__ == "__main__":
    raise SystemExit(c.cli(evaluate))
