# -*- coding: utf-8 -*-
import sys
import os
import os.path
import re
from exceptions import SystemExit

# user-defined module
import netlistx.netlist_util as nu
import netlistx.class_circuit   as cc
from netlistx.parser.netlist_parser import vm_parse

from netlistx.scan.config import SCAN_LIB2 as SCAN_LIB

__all__ = [ "insert_scan_chain_new" ]

#�������ɨ����ĺ�׺
_SUFFIX = "_full_scan_using_lut"

def insert_scan_chain_new(fname, verbose=False, presult=True,\
                input_file_dir = os.getcwd(), output_file_dir = os.getcwd(),\
                K = 6):
    '''@para: fname ,input file name in current path
             verbose, if True print ���õĸ��������� redandunt infomation
             presult ,if True ��ӡ���յĸ���ͳ����Ϣ
             input_file_dir, default os.getcwd(),
             output_file_dir, default os.getcwd()
    '''
    input_file=os.path.join(input_file_dir , fname)    

    #file -->> m_list
    info = vm_parse( input_file )
    m_list = info['m_list']
    port_decl_list   = info['port_decl_list']
    signal_decl_list = info['signal_decl_list']
    assign_stm_list  = info['assign_stm_list']
   
    nu.mark_the_circut(m_list[1:])
    
    #m_list -->>all info need 
    lut_type_cnt = [0,0,0,0,0,0]
    all_fd_dict  = nu.get_all_fd(m_list, verbose)
    all_lut_dict = nu.get_all_lut(m_list, lut_type_cnt, verbose) 
    
    ##���������б��¼����Ҫ�����޸ĵ�LUT��D��������
    lut_out2_FD_dict,FD_din_lut_list        =nu.get_lut_cnt2_FD(m_list,all_fd_dict,verbose,K)    
    
    ##CE�Ż�����Ҫ��netlist��Ϣ
    ce_signal_list,fd_has_ce_list           =nu.get_ce_in_fd(all_fd_dict,verbose)
    lut_cnt2_ce,un_opt_ce_list              =nu.get_lut_cnt2_ce(m_list,ce_signal_list,K,verbose)
    fd_ce_cnt = len(fd_has_ce_list)
    
    #gt.generate_testbench(m_list[0],fd_cnt=len(all_fd_dict),output_dir=output_file_dir)    
    #####################################################################    
    counter=0
    scan_out_list=[]
    gatedce_list = []

    #cnt for debug only
    fd_replace_cnt=0
    cnt_edited_lut=0
    #cnt for debug only 
    
    name_base = os.path.splitext(fname)[0]
    output_file = os.path.join(output_file_dir, name_base + _SUFFIX + '.v')
    try:
        fobj=open(output_file,'w')
    except IOError,e:
        print "Error: file open error:",e
        raise SystemExit
    fobj.writelines(SCAN_LIB)

    #--------------------------------------------------------------------------
    #���Ӷ���ɨ��˿�
    #--------------------------------------------------------------------------
    add_scan_ports_top(m_list[0])    

    #--------------------------------------------------------------------------
    #primitive���޸�
    #--------------------------------------------------------------------------
    for eachPrimitive in m_list[1:]:
        ##�޸�LUT����MUX,����ɨ�蹦�ܲ���
        if eachPrimitive.m_type=='LUT' and (eachPrimitive.name in lut_out2_FD_dict.keys()):
            counter += 1
            fusion_lut_with_mux(eachPrimitive, counter)
            fd_name = lut_out2_FD_dict[eachPrimitive.name][1]
            scan_out_list.append( all_fd_dict[fd_name]['Q'].string )
            cnt_edited_lut += 1
        #δ������ʣ��LUT��FD������CELL�滻���˿�����
        elif (eachPrimitive.m_type=='FD') and (eachPrimitive.name not in FD_din_lut_list):
            counter += 1
            replace_fd_with_scan_fd(eachPrimitive, counter)
            scan_out_list.append('scan_out' + str(counter))
            fd_replace_cnt+=1
        #CEʱ��ʹ�ܿ����źŵ��Ż�. ��LUT,����ʱ��ʹ�ܵĲ���,���ǲ���һ������
        elif(eachPrimitive.m_type=='LUT') and (eachPrimitive.name in lut_cnt2_ce):
            fusion_lut_with_or(eachPrimitive)

    #--------------------------------------------------------------------------
    # δʹ��LUT�����gate �� ce�ź�����Ӧ���޸�, ��֮��assign���ֵ���ͬ
    #--------------------------------------------------------------------------
    for eachPrimitive in m_list[1:]:
        if (eachPrimitive.m_type=='FD') and (eachPrimitive.name in fd_has_ce_list):
            current_ce = all_fd_dict[eachPrimitive.name]['CE'].string 
            if current_ce in un_opt_ce_list:
                gatedCE = gate_ce( current_ce )
                new_ce_signal = cc.signal('wire', gatedCE)
                eachPrimitive.edit_spec_port('CE', new_ce_signal)
                #��Ϊ���FD�������ӵ���ͬ��CE, signal_decl_list�������ظ�������.
                if not gatedCE in gatedce_list:
                    gatedce_list.append(gatedCE)
                    signal_decl_list.append(new_ce_signal)

    #--------------------------------------------------------------------------
    #ɨ����˳���ȷ��,�ڽ�β������assign
    #--------------------------------------------------------------------------
    assign_stm_list.append( cc.assign('assign', cc.signal(name = "scan_in1"),
                                                cc.signal(name = "scan_in")) )
    for i in range(2,counter+1):
        tmp_assign = cc.assign('assign',cc.signal(name = "scan_in"+str(i) ),
                                        cc.signal( name = scan_out_list[i-2] )) 
        assign_stm_list.append( tmp_assign )
    assign_stm_list.append(cc.assign('assign',cc.signal( name = "scan_out"), 
                                cc.signal( name = scan_out_list[counter-1])) )
    
    #--------------------------------------------------------------------------
    #����Ƿ�ɹ�
    #check all the numbers ,insure all wanted LUT and FD been handled
    #--------------------------------------------------------------------------
    assert (fd_replace_cnt + cnt_edited_lut) == len(all_fd_dict), "Not all the FD has been scaned !!"
    assert (cnt_edited_lut == len(FD_din_lut_list) ), "There is Usefully LUT not edited !!"

    #--------------------------------------------------------------------------
    #�����ļ��Ĵ�ӡ����ֱ�������stdout����
    #--------------------------------------------------------------------------
    if fobj:
        console = sys.stdout
        sys.stdout = fobj
        m_list[0].print_module()
        for eachPipo in port_decl_list:
            eachPipo.__print__(pipo_decl = True)
        for eachWire in signal_decl_list:
            eachWire.__print__(is_wire_decl = True)
        for eachModule in m_list[1:]:
            assert isinstance(eachModule, cc.circut_module), eachModule
            print eachModule
        if assign_stm_list:
            for eachAssign in assign_stm_list:
                print eachAssign
        for eachCE in un_opt_ce_list:
            print "assign %s = scan_en? 1'b1 : %s ;"%(gate_ce(eachCE), eachCE)
        print "//this is a file generate by @litao"
        print "endmodule"
        sys.stdout=console
    fobj.close()
    #--------------------------------------------------------------------------
    #�������ݵĴ�ӡ���
    #--------------------------------------------------------------------------
    if presult:
        print 'Info:LUT cnt is      : '+str(len(all_lut_dict.keys()))
        print 'Info:LUT1-6 number is: '+str(lut_type_cnt)
        print 'Info:FD CNT is       : '+str(counter)+":::"+str(len(all_fd_dict))
        print 'Info:replace FD CNT  : '+str(fd_replace_cnt)
        print 'Info:Useful LUT CNT  : '+str(len(FD_din_lut_list))
        print 'Info:edited LUT CNT  : '+str(cnt_edited_lut)
        print 'Info:FD has a CE CNT : '+str(fd_ce_cnt)
        print 'Info:ce_signal CNT is: '+str(len(ce_signal_list))
    print 'Job: Full Scan insertion of  %s done\n\n' % fname
    return True

def add_scan_ports_top(top_module):
    '''�ڶ���ģ�����������˿�
    '''
    #assert isinstance(top_module, cc.circut_module)
    _scan_in = cc.signal('input', 'scan_in', None)
    _scan_en = cc.signal('input', 'scan_en', None)
    _scan_out = cc.signal('output', 'scan_out', None)
    port_scan_in = _scan_in.signal_2_port()
    port_scan_en = _scan_en.signal_2_port()
    port_scan_out = _scan_out.signal_2_port()
    top_module.port_list.insert(0,port_scan_in)
    top_module.port_list.insert(0,port_scan_out)
    top_module.port_list.insert(0,port_scan_en)
    return None

def fusion_lut_with_mux( lut, counter ):
    '''��lut��mux�����߼����, ����ɨ���߼�.
        In = scan_in+str(counter)
        I(n+1) = scan_en
        �����µ�init_value
    '''
    assert isinstance(lut, cc.circut_module) and lut.m_type=="LUT"
    input_num = lut.input_count()
    assert input_num == int( lut.cellref[3] )
    scan_in = cc.port("I"+str(input_num),'input',cc.signal(name="scan_in"+str(counter)))            
    scan_en = cc.port('I'+str(input_num+1),'input',cc.signal(name="scan_en"))            
    lut.port_list.insert(-1,scan_in)
    lut.port_list.insert(-1,scan_en)
    assert (not lut.param_list==None) and len(lut.param_list)==1
    old_init = lut.param_list[0].value
    init_legal = re.match('(\d+)\'[hb]([0-9A-F]+)',old_init)
    assert (init_legal is not None)
    assert int(init_legal.groups()[0])==2**input_num
    if input_num == 1:
        assert  (init_legal.groups()[0] == '2' and init_legal.groups()[1] == "1"),\
        "Error:find LUT1 .INIT !=2'h1 %s, is %s" % (lut.name,lut.param_list[0].value)
        NEW_INIT = "8'hC5"
    else:
        NEW_INIT = str(2**(input_num+2))+'\'h'+'F'*int(2**(input_num-2)) \
        +'0'*int(2**(input_num-2))+(init_legal.groups()[1])*2
    lut.param_list[0].edit_param('INIT',NEW_INIT)
    lut.cellref = re.sub('LUT[1-4]', ( 'LUT'+str(input_num+2) ), lut.cellref )
    assert lut.input_count() == (input_num + 2)
    return None

def replace_fd_with_scan_fd(fd, counter):
    '''��FD*�滻Ϊ SCAN_FD*, ��������������ɨ���йصĶ˿�.
    '''
    assert isinstance(fd, cc.circut_module) and fd.m_type == "FD"
    fd.cellref = "SCAN_"+fd.cellref
    SCAN_IN = cc.port( 'SCAN_IN', 'input', cc.signal(name="scan_in"+str(counter)) )
    SCAN_EN = cc.port( 'SCAN_EN', 'input', cc.signal(name="scan_en"))
    SCAN_OUT = cc.port( 'SCAN_OUT', 'output', cc.signal(name='scan_out'+str(counter)) )
    fd.port_list.insert(0, SCAN_OUT)
    fd.port_list.insert(0, SCAN_EN)
    fd.port_list.insert(0, SCAN_IN)
    return None

def fusion_lut_with_or(lut):
    '''��LUT�� or���߼����.������: O' = (In == 1'b1) ? 1'b1: O ;
    '''
    input_num = int(lut.cellref[3])
    scan_en = cc.port('I'+str(input_num),'input',cc.signal(name="scan_en"))
    lut.port_list.insert(-1,scan_en)
    assert (not lut.param_list==None)
    assert len(lut.param_list)==1
    old_init=lut.param_list[0].value
    init_legal=re.match('(\d+)\'[hb]([0-9A-F]+)',old_init)
    assert (init_legal is not None)
    assert int(init_legal.groups()[0])==2**input_num
    if input_num==1:
        NEW_INIT="4'hD"
    else:
        NEW_INIT=str(2**(input_num+1))+'\'h'+'F'*int(2**(input_num-2))\
                    +init_legal.groups()[1]
    lut.param_list[0].edit_param('INIT',NEW_INIT)
    lut.cellref = re.sub('LUT[1-5]', ('LUT' + str(input_num+1)), lut.cellref)
    return None

def gate_ce(current_ce):
    '''��current_ce��������, ����������
    '''
    # if current ce start with \ , there will be a syntax error to synthesis
    # ����������źŸ�����Ӧ�ò���������⣬ԭ�е��ź���ȫ���䣬ֻ�ǰ����ӵ�FD���ź�
    # �����������һ��gated_ prefix�������е��ź����Ƶ� ".[]" ȫ��� "_",����µ��ź�����
    if current_ce[0] == '\\':
        gatedCE = "gated_" + re.sub("[\[\]\.]", "_", current_ce[1:])
    else:
        gatedCE = "gated_" + re.sub("[\[\]\.]", "_", current_ce)
    return gatedCE

#############################################################################################
if __name__=='__main__':
    if len(sys.argv) == 1:
        print "single-file mode in ", os.getcwd()
        fname = raw_input("plz enter the file name:")
        k = int( raw_input("plz enter K:") )
        insert_scan_chain_new(fname, K = k )

    elif sys.argv[1]=='-batch': 
        print "batch mode", os.getcwd()         
        pwd = ""
        while(not os.path.exists(pwd)):
            pwd = raw_input("plz enter vm files path:")
        outpath = os.path.join(pwd, "full_using_lut")
        if not os.path.exists( outpath ):
            os.mkdir(outpath)
        K=int( raw_input('plz enter the K parameter of FPGA:K=') )
        assert (K==6 or K==4),"K not 4 or 6"
        for eachFile in os.listdir(pwd):
            if os.path.splitext(eachFile)[1] in ['.v','.vm']:
                print "Inserting scan for ", eachFile
                insert_scan_chain_new(eachFile, False, True, pwd ,outpath, K)
