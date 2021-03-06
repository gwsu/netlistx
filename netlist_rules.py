# -*- coding:utf-8 -*-

from netlistx import circuit as cc
from netlistx.exception import *
from netlistx.netlist import Netlist


def check(nt, check_clk = True, check_reset = True):
    '''
    '''
    check_ports =  ['C','R','S','CLR','PRE']
    specials = _get_fd_specport( nt, check_ports)

    clks = specials['C']
    sync_resets  = specials['R'].keys() + specials['S'].keys()
    async_resets = specials['CLR'].keys() + specials['PRE'].keys()
    if check_clk:
        _clk_check(nt, clks)
    if check_reset:
        _reset_check( nt, sync_resets + async_resets)

def _get_fd_specport(nt, port_names ):
    '''@param: nt, a Netlist obj
       @return: specs, a dict, {port_name:{signal_id : [fd list]} }
    '''
    assert isinstance(nt, Netlist)
    fds = [prim for prim in nt.primitives if prim.m_type == 'FD']
    specs = {name:{} for name in port_names }
    for fd in fds:
        for port in fd.port_list:
            name = port.port_name
            if name in port_names:
                signal_id = port.port_assign.string
                if not specs[name].has_key( signal_id ):
                    specs[name][ signal_id ] = [fd]
                else:
                    specs[name][ signal_id ].append( fd )
    return specs

def _clk_check(nt, clks):
    if len(clks) > 1:
        errmsg =  "Netlist has %s CLK domain.They are: %s" % ( len(clks), clks.keys() )
        raise CrgraphError, errmsg
    elif len(clks) == 0:
        print "Info: no clks in this netlist"
        return None
    clkname = clks.keys()[0]
    clkflag = False
    single_inports = []
    for port in nt.ports:
        if port.port_type == cc.port.PORT_TYPE_INPUT:
            single_inports += port.split()
    for port in single_inports:
        if port.port_assign.string == clkname:
            clkflag = True
            break
        else: continue
    if not clkflag:
        errmsg = "CLK: %s do not connected to any pi" % clkname
        raise CrgraphError, errmsg 

def _reset_check(nt, resets):
    single_inports = []
    for port in nt.ports:
        if port.port_type == cc.port.PORT_TYPE_INPUT:
            single_inports += port.split()
    strings = [port.port_assign.string for port in single_inports]
    internal_resets = []
    for reset in resets:
        if reset not in strings:
            internal_resets.append( reset)
    if internal_resets:
        errmsg = "Internal Resets: %s" % internal_resets
        raise CrgraphError, errmsg 
    