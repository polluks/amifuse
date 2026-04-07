"""
Helpers to poke ExecBase/Task structures directly in vamos memory to create a
minimal task context and MsgPort for the filesystem handler. This is hacky but
avoids modifying amitools internals.
"""

from amitools.vamos.libstructs.exec_ import TaskStruct, NodeType, MsgPortStruct, ListStruct  # type: ignore
from amitools.vamos.schedule.stack import Stack  # type: ignore
from amitools.vamos.schedule.task import Task  # type: ignore
from amitools.vamos.libstructs.dos import DosPacketStruct, MessageStruct  # type: ignore
from amitools.vamos.machine.regs import REG_A0, REG_A6, REG_A7  # type: ignore


def create_task(vh, stack_size=8192, name="handler_task"):
    alloc = vh.alloc
    mem = alloc.get_mem()
    tsk_mem = alloc.alloc_memory(TaskStruct.get_size(), label=name)
    tsk = TaskStruct(mem, tsk_mem.addr)
    tsk.node.type.val = NodeType.NT_TASK
    stack = Stack.alloc(alloc, stack_size, name=name + "_stack")
    tsk.sp_upper.aptr = stack.get_upper()
    tsk.sp_lower.aptr = stack.get_lower()
    tsk.sp_reg.aptr = stack.get_initial_sp()
    return tsk_mem.addr, stack


def set_this_task(vh, task_bptr):
    mem = vh.alloc.get_mem()
    exec_base_addr = mem.r32(4)
    # ExecBase at addr; ThisTask at offset 276 (tc_CurrentTask) in exec V33+, here we hardcode offset for simplicity
    # For simplicity, assume ExecBase struct at least has ThisTask at offset 276 (0x114) as in 2.0+
    this_task_off = 0x114
    mem.w32(exec_base_addr + this_task_off, task_bptr)


def create_msgport(vh, task_bptr):
    alloc = vh.alloc
    mem = alloc.get_mem()
    mp_mem = alloc.alloc_memory(MsgPortStruct.get_size(), label="MsgPort")
    mp = MsgPortStruct(mem, mp_mem.addr)
    mp.node.type.val = NodeType.NT_MSGPORT
    mp.flags.val = 0
    mp.sig_bit.val = 0
    mp.sig_task.aptr = task_bptr << 2
    # init list
    lst = ListStruct(mem, mp_mem.addr + 20)
    lst.head.aptr = 0
    lst.tail.aptr = 0
    lst.tail_pred.aptr = 0
    lst.type.val = NodeType.NT_MESSAGE
    return mp_mem.addr


def build_packet(mem, alloc, msg_port_bptr, pkt_type, args):
    pkt_mem = alloc.alloc_memory(DosPacketStruct.get_size(), label="DosPacket")
    msg_mem = alloc.alloc_memory(MessageStruct.get_size(), label="PacketMsg")
    pkt = DosPacketStruct(mem, pkt_mem.addr)
    msg = MessageStruct(mem, msg_mem.addr)
    pkt.link.aptr = msg_mem.addr
    pkt.port.aptr = msg_port_bptr << 2
    pkt.type.val = pkt_type
    # fill args
    for i, val in enumerate(args[:7], start=1):
        pkt.sfields.get_field_by_name(f"dp_Arg{i}").val = val
    # message
    msg.node.type.val = NodeType.NT_MESSAGE
    msg.reply_port.aptr = msg_port_bptr << 2
    msg.length.val = MessageStruct.get_size()
    # link msg name to packet
    msg.node.name.aptr = pkt_mem.addr
    return pkt_mem.addr, msg_mem.addr


def start_handler(vh, fssm_bptr, entry_addr, stack_size=8192):
    task_addr, stack = create_task(vh, stack_size=stack_size, name="handler_task")
    set_this_task(vh, task_addr >> 2)
    # set exec StackSwap bounds for this task
    if hasattr(vh.slm, "exec_impl"):
        vh.slm.exec_impl.stk_lower = stack.get_lower()
        vh.slm.exec_impl.stk_upper = stack.get_upper()
    mem = vh.alloc.get_mem()
    exec_base_addr = mem.r32(4)
    start_regs = {REG_A0: fssm_bptr << 2, REG_A6: exec_base_addr, REG_A7: stack.get_initial_sp()}
    task = Task("handler_task", entry_addr, stack, start_regs=start_regs)
    vh.scheduler.add_task(task)
    return task_addr
