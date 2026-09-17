import random
import sys

import jpamb
import jvm
import jvm.state as jvmc

def binary(op, v1: int, v2: int) -> int | str:
    match op:
        case jvm.BinaryOpr.Div:
            try:
                return v1 // v2
            except ZeroDivisionError:
                return "divide by zero"

        case jvm.BinaryOpr.Sub:
            return v1-v2

        case jvm.BinaryOpr.Add:
            return v1+v2

        case jvm.BinaryOpr.Mul:
            return v1*v2

        case jvm.BinaryOpr.Rem:
            return v1%v2

        case a:
            raise NotImplementedError(f"Unhandled binary {op!r}")


def compare(op, v1: int, v2: int) -> bool:
    match op:
        case jvm.CmpOpr.Eq:
            return v1 == v2
        case jvm.CmpOpr.Ne:
            return v1 != v2
        case jvm.CmpOpr.Eq:
            return v1 == v2
        case jvm.CmpOpr.Lt:
            return v1 < v2
        case jvm.CmpOpr.Le:
            return v1 <= v2
        case jvm.CmpOpr.Ge:
            return v1 >= v2
        case jvm.CmpOpr.Gt:
            return v1 > v2
        case _:
            raise NotImplementedError(f"Unhandled comparation {op!r}")


def step(bc: jpamb.Bytecode, state: jvmc.State) -> tuple[jvmc.PC, jvmc.State | str]:
    assert isinstance(state, jvmc.State), f"expected state but got {state}"
    frame = state.frames.peek()
    pc = frame.pc
    opr = bc[pc]
    output = state
    print(f"Stepping {pc}:\n > {opr}", file=sys.stderr)
    match opr:
        case jvm.Dup():
            v1 = frame.stack.pop()
            frame.stack.push(v1)
            frame.stack.push(v1)
            frame.pc += 1

        case jvm.Ifz(condition=c, target=t):
            assert isinstance (c,jvm.CmpOpr), f"expected comparison op, but got {type(c)}"
            assert isinstance (t, int), f"expected int, but got {type(t)}"

            v1 = frame.stack.pop()
            assert (isinstance(v1, jvmc.StackInt) or isinstance(v1,jvmc.StackReference)), f"expected int or reference, but got {v1}"
            result = compare(c, v1.value, 0)
            
            if isinstance(result, str):
                output = result
            else:
                frame.pc = pc%t if result else frame.pc + 1

        case jvm.Load(type=t, index=n):
            v = frame.locals[n]
            frame.stack.push(v)
            frame.pc += 1

        case jvm.ArrayLoad(type=t):
            index, arr_ref = frame.stack.pop(),frame.stack.pop()
            if arr_ref.value == 0:
                output = "NullPointerException"
            else:
                arr = state.heap[arr_ref]
                if index.value < 0 or index.value >= len(arr.values):
                    output = "out of bounds"
                else:
                    arr = state.heap[arr_ref]
                    
                    val = arr.values[index.value]
                    frame.stack.push(jvmc.StackInt(val))
                    
                    frame.pc += 1

        case jvm.Incr(index=i, amount=a):
            current_val = frame.locals[i].value
            frame.locals[i] = jvmc.StackInt(current_val + a)
            frame.pc += 1

        case jvm.Goto(target=t):
            frame.pc = frame.pc%t

        case jvm.Push(type=t, value=v):
            if isinstance(t, jvm.Int):
                frame.stack.push(jvmc.StackInt(v))
            elif isinstance(t,jvm.Float):
                frame.stack.push(jvmc.StackFloat(v))
            elif isinstance(t,jvm.Reference):
                frame.stack.push(jvmc.StackReference(v))
            else:
                raise NotImplementedError(f"Push type {t} not supported!")
                
            frame.pc += 1

        case jvm.Push(type=t, value=v):
            if t is jvm.Int():
                frame.stack.push(jvmc.StackInt(v))
            else:
                raise NotImplementedError("Error")
            frame.pc += 1

        case jvm.Binary(type=jvm.Int(), operant=op):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert isinstance(v1, jvmc.StackInt), f"expected int, but got {v1}"
            assert isinstance(v2, jvmc.StackInt), f"expected int, but got {v2}"

            value = binary(op, v1.value, v2.value)

            if isinstance(value, str):
                output = value
            else:
                frame.stack.push(jvmc.StackInt(value))
                frame.pc += 1

        case jvm.Return(type=t):
            val = None
            if t is not None:
                val = frame.stack.pop()

            state.frames.pop()

            if state.frames and val:
                frame = state.frames.peek()
                frame.stack.push(val) 
            else:
                output = "ok"

        case jvm.Get(static=True, field=field):
            # Hack - Only handle the assertion case
            assert field.extension.name == "$assertionsDisabled"

            # Hack - Assuming assertions are never disabled
            frame.stack.push(jvmc.StackInt(0))
            frame.pc += 1

        case jvm.New(classname=jvm.ClassName("java.lang.AssertionError")):
            # Hack -- if we create an assertion error, we probably also throw it.
            output = "assertion error"

        case jvm.If(condition=c,target=t):
            val2,val1 = frame.stack.pop(), frame.stack.pop()
            result = compare(c, val1.value, val2.value)
            
            if isinstance(result, str):
                output = result
            else:
                frame.pc = pc%t if result else frame.pc + 1

        case jvm.NewArray(type=t, dim=d):
            size = frame.stack.pop()
            if size.value < 0:
                output = "Negative Size Array Exception"
                return
            initial_values = [0] * size.value
            arr = jvmc.HeapArray(contains=t, values=initial_values)
            ref = state.heap.new(arr)
            frame.stack.push(ref)
            frame.pc += 1

        case jvm.ArrayStore(type=t):
            val, index, ref = frame.stack.pop(), frame.stack.pop(), frame.stack.pop()
            
            if ref.value == 0:
                output = "null pointer"
            else:
                arr = state.heap[ref]
                if index.value < 0 or index.value >= len(arr.values):
                    output = "out of bounds"
                else:
                    arr.values[index.value] = val.value
                    frame.pc += 1

        case jvm.Store(type=t,index=i):
            val = frame.stack.pop()
            frame.locals.locals[i] = val
            frame.pc+=1

        case jvm.ArrayLength():
            arr_ref = frame.stack.pop()
            
            if arr_ref.value == 0:
                output = "null pointer"
            else:
                arr = state.heap[arr_ref]
                
                length_value = len(arr.values)
                frame.stack.push(jvmc.StackInt(length_value))
                
                frame.pc += 1

        case jvm.InvokeStatic(method=m):
            #to be finished (Calls, loops, Strings)
            return

        case a:
            raise NotImplementedError(a.help())

    assert isinstance(output, (jvmc.State, str))

    return pc, output


def initial(bc: jpamb.Bytecode, methodid: jvm.AbsMethodID, input: jpamb.Input):
    frame = jvmc.Frame.from_method(bc.getmethod(methodid))
    state = jvmc.State(jvmc.Heap(), jvmc.CallStack.from_frames([frame]))
    for i, v in enumerate(input.values):
        # Convert arbitrary values into local values
        match v:
            case jpamb.case.Boolean(value):
                frame.locals[i] = jvmc.StackInt(1 if value else 0)
            case jpamb.case.Int(value):
                frame.locals[i] = jvmc.StackInt(value)
            case jpamb.case.Array(contains=type, values=values):
                match type:
                    case jvm.Char():
                        ref = state.heap.new(
                            jvmc.HeapArray(type, [ord(a) for a in values])
                        )
                    case jvm.Int():
                        ref = state.heap.new(jvmc.HeapArray(type, [a for a in values]))
                frame.locals[i] = ref
            case jpamb.case.String(value=value):
                ref = state.heap.new(jvmc.HeapString(value))
                frame.locals[i] = ref
            case a:
                raise NotImplementedError(
                    f"Do not know how to convert values of type {a!r} to a local value"
                )

    return state


def interpret():
    """The entry point for the interpreter"""

    methodid, input, max_steps = jpamb.getcase(
        "dynamic",
        "1.0",
        "The Rice Theorem Cookers",
        ["dynamic", "python"],
        for_science=True,
    )

    suite, eff = jpamb.setup()
    bc = jpamb.Bytecode(suite, eff, {})

    state = initial(bc, methodid, input)

    last = jpamb.emit_init(state)

    for x in range(max_steps):
        pc, state = step(bc, state)
        last = jpamb.emit_step(last, pc, state)

        if isinstance(state, str):
            break


def fuzz_input(rand: random.Random, methodid: jvm.AbsMethodID) -> jpamb.case.Input:
    input = []
    # 1. come up with possible inputs
    for p in methodid.extension.params:
        match p:
            case jvm.Int():
                input.append(jpamb.case.Int(rand.randint(-(1 << 31), 1 << 31)))
            case jvm.Boolean():
                input.append(jpamb.case.Boolean(1 == rand.randint(0, 1)))
            case a:
                raise NotImplementedError(
                    "Don't know how to create random values for {input}"
                )

    return jpamb.case.Input(input)


def analyse():
    """The dynamic analysis, e.g. in this case a (dumb) fuzzer."""

    methodid = jpamb.getmethodid(
        "dynamic",
        "1.0",
        "The Rice Theorem Cookers",
        ["dynamic", "python"],
        for_science=True,
    )

    suite, eff = jpamb.setup()
    bc = jpamb.Bytecode(suite, eff, {})

    MAX_STEPS = 200

    import random

    # Make the randomness deterministic
    rand = random.Random(0)

    behaviors = set()
    # Try 10 random inputs
    for i in range(10):
        input = fuzz_input(rand, methodid)
        state = initial(bc, methodid, input)

        for x in range(MAX_STEPS):
            _, state = step(bc, state)
            if isinstance(state, str):
                behaviors.add(state)
                break

    for query in jpamb.QUERIES:
        if query in behaviors:
            if query == "*":
                print(f"{query};timeout")
            else:
                print(f"{query};found")
        else:
            print(f"{query};not-found")
