# -*- coding: utf-8 -*-
"""
Created on Tue Aug 25 22:28:45 2015
@author: litao
@e-mail:litaotju@qq.com
address:Tianjin University
"""
import networkx as nx
import class_circuit as cc
from circuitgraph import CircuitGraph
###############################################################################


class CloudRegGraph(nx.DiGraph):
    '''
        本图的节点分为两类，一类是cloud,也就是一个有向子图。一类是reg,也就是FD primitive
        子图中有存储了关于组合逻辑节点的互联信息
    '''
    def __init__(self, basegraph ):
        nx.DiGraph.__init__(self)
        self.clouds=[]
        self.regs=[]
        assert isinstance(basegraph, CircuitGraph) ,"%s" % basegraph.__class__
        self.__get_cloud_reg_graph(basegraph)

    def __get_cloud_reg_graph(self, basegraph):
        '''
            -->>basegraph.cloud_reg_graph.copy()
            Model the circuit graph to a cloud(combinational cone) and register(FD)
            graph,add a .cloud_reg_graph data to basegraph.
            注意：1.现有的cloud_register图中没有包含pipo节点，只是prim的节点
                 2.函数不仅为调用它的对象增加了一个 cloud_reg_graph数据，最终返回了该图的深度复制
            待续：现有的算法是先去掉所有的FD，将剩下的连通分量合并成一个cloud。实际上如果剩下的图不
                 连通，那么它们在电路中可以合并成一个子图吗?
        '''
        # g2是一个用basegraph中的点和边建立的无向图，
        # 所以基本的节点和basegraph的节点是完全一致的，
        # 每一个节点都指向了m_list当中的原语的  cc.circuit_module() 对象的实例化
        g2=nx.Graph()
        g2.add_nodes_from(basegraph.prim_vertex_list)
        for eachEdge in basegraph.prim_edge_list:
            g2.add_edge(eachEdge[0][0],eachEdge[0][1])
            
        #------------------------------------------------------
        #step1 找出所有FD节点，并移去FD节点
        fd_list=[]
        for eachFD in basegraph.prim_vertex_list:
            if eachFD.m_type == 'FD' :
                fd_list.append(eachFD)
        print "Info:%d fd has been found " % len(fd_list)
        g2.remove_nodes_from(fd_list)

        #------------------------------------------------------
        #step2 找出连通分量,建立子图
        compon_list = []
        for c in nx.connected_components(g2):
            #连通子图            
            ccsub = g2.subgraph(c)
            compon_list.append(ccsub)
        print "Info: %d connected_componenent subgraph after remove FD" % len(compon_list)

        #step2.1 
        #将每一个连通分量，也就是子图恢复为有向图，这样做的目的是搞清楚组合逻辑之间的连接关系
        #由于不存在组合逻辑回路，所以理论上，将全是组合的子图转换成有向图，边的数目完全相等
        #这可以通过下面的打印信息来查看
        #l2是compon_list的有向图版
        l2=[]
        for eachSubgraph in compon_list:
            h = nx.DiGraph(eachSubgraph)
            if eachSubgraph.number_of_nodes()>1:
                for eachEdge in h.edges():
                    if not basegraph.has_edge(eachEdge[0], eachEdge[1]):
                        h.remove_edge(eachEdge[0], eachEdge[1])
            l2.append(h)

        #------------------------------------------------------
        #step3 记录下fd的D Q 端口与其他FD以及 与组合逻辑的有向边，以及节点
        special_edges=[]
        reg_reg_edges=[]
        fd_linked_nodes_edges={}
        for x in basegraph.prim_edge_list:
           for eachNode in x[0]:
               if eachNode.m_type == 'FD':
                  tmp= 1 if x[0].index(eachNode)==0 else 0
                  fd_port = x[1][1-tmp] #记录下来现在的FD的端口
                  other_prim = x[0][tmp]
                  other_port = x[1][tmp]
                  if (other_prim.m_type != 'FD') and (fd_port.name in ['D','Q']):
                      non_fd_prim = other_prim
                      if not fd_linked_nodes_edges.has_key(non_fd_prim):
                          fd_linked_nodes_edges[non_fd_prim] = []
                      fd_linked_nodes_edges[non_fd_prim].append(x)
                  elif other_prim.m_type == 'FD' and (fd_port.name in ['D','Q'] ) and\
                      other_port.port_name in ['D','Q']:
                      reg_reg_edges.append(x)
                  else:
                      special_edges.append(x)

        #------------------------------------------------------
        #step4
        #新建一个有向图，节点为 cloud（step2获得的连通分量）+fd（step1获得）
        #              边为fd-cloud或者 fd-fd 的有向连接（step3获得）
        # vertex
        self.__add_clouds_from(l2)
        self.__add_regs_from(fd_list)
        # edge        
        for eachSubgraph in l2:
            for eachNonFdPrim in fd_linked_nodes_edges.keys():
                if eachSubgraph.has_node(eachNonFdPrim):
                    tmp_edge_list = fd_linked_nodes_edges[eachNonFdPrim]
                    for eachEdge in tmp_edge_list:
                        if eachEdge[0][0] == eachNonFdPrim:
                            ##注意，在这用等号是合法的，因为他们两都是原来的prim_vertex_set
                            ##在新添加边的时候，保留了在原图中的边的信息
                            self.add_edge(eachSubgraph, eachEdge[0][1], original_edge=eachEdge)
                        else:
                            assert eachEdge[0][1] == eachNonFdPrim
                            self.add_edge(eachEdge[0][0], eachSubgraph, original_edge=eachEdge)
        ##注意，在reg_reg_edges当中，边的元素，就是fd_list当中的module对象。所以这样做不会增加新的边
        for eachEdge in reg_reg_edges:
            # self.add_edge(eachEdge[0][0], eachEdge[0][1], original_edge=eachEdge)
            # 在reg-reg 之间插入一个空的网络
            empty_cloud = nx.DiGraph()
            self.add_edge(eachEdge[0][0], empty_cloud, original_edge = eachEdge)
            self.add_edge(empty_cloud, eachEdge[0][1], original_edge = eachEdge)
            self.clouds.append(empty_cloud)
        
        # ---------------------------------------------------------------------
        # step5 把FD合并成REG,把与之相连接的CLOUD 也合并
        self.__check_rules()
        self.__merge_fd_cloud()
        self.__check_rules()
        basegraph.cloud_reg_graph = self  #把新图 连接给旧图
        print "Note: get_cloud_reg_graph()"     
        # return self.copy()
        return None
    
    # featured 8.26    
    def __merge_fd_cloud(self):
        '合并多个cloud'
        for eachFD in self.regs:
            succs = self.successors(eachFD)
            if len(succs) <= 1:
                continue
            else:
                big_cloud = nx.union_all( succs )
            pre_fds = set()
            succ_fds = set()
            for succ_cloud in self.successors(eachFD):
                pre_fds = pre_fds.union( set(self.predecessors(succ_cloud) ))
                succ_fds = succ_fds.union( set(self.successors(succ_cloud)) )
                self.remove_node(succ_cloud)   
            self.add_node(big_cloud)
            for pre_fd in pre_fds:
                self.add_edge(pre_fd, big_cloud)
            for succ_fd in succ_fds:
                self.add_edge(big_cloud, pre_fd)
        # step2 合并所有的FD 成为一个REG
#        self.big_regs = []
        self.big_clouds = []
#        rc_edge = [] # reg-cloud edges found
        for node in self.nodes_iter():
            if isinstance(node , nx.DiGraph):
                cloud = node   
                self.big_clouds.append( cloud )
#                # cloud前与后的寄存器序列
#                reg_pre = nx.DiGraph()
#                reg_succ = nx.DiGraph()                
#                reg_pre.add_nodes_from( self.predecessors(cloud) )
#                reg_succ.add_nodes_from( self.successors(cloud) )
#                # 将前一级寄存器
#                self.big_regs.append( reg_pre )
#                self.big_regs.append(reg_succ)
#                #将reg-cloud 边存储下来
#                rc_edge.append( (reg_pre, cloud) ) 
#                rc_edge.append( (cloud, reg_succ) )
#        self.remove_nodes_from(self.regs) #移去所有的小FD
#        self.add_edges_from()
                
    def __add_clouds_from(self, list1):
        for eachCloud in list1:
            assert isinstance(eachCloud, nx.DiGraph)
            self.clouds.append(eachCloud)
            self.add_node(eachCloud)

    def __add_regs_from(self, list1):
        for eachFD in list1:
            assert isinstance(eachFD, cc.circut_module) and\
                eachFD.m_type == 'FD', eachFD.name
            self.add_node(eachFD)
            self.regs.append(eachFD)
 
    def paint(self):
        label_dict={}
        for eachCloud in self.clouds:
            if eachCloud.number_of_nodes()>1:
                label_dict[eachCloud]='cloud'
            else:
                node=eachCloud.nodes()[0]
                label_dict[eachCloud]=node.cellref+":"+node.name
        for eachReg in self.regs:
            label_dict[eachReg]=eachReg.cellref+":"+eachReg.name
        ps=nx.spring_layout(self)
        nx.draw_networkx_nodes(self,pos=ps,nodelist=self.clouds,node_color='r')
        nx.draw_networkx_nodes(self,pos=ps,nodelist=self.regs,node_color='g')
        nx.draw_networkx_edges(self,ps)
        nx.draw_networkx_labels(self,ps,labels=label_dict)
        return True

    def info(self):
        print "Cloud_Reg_graph info:-----------------"
        print nx.info(self)
        ncloud = 0
        nreg = 0
        for node in self.nodes_iter():
            if isinstance(node, nx.DiGraph): 
                ncloud += 1
            else:
                nreg += 1
        print "Number of cloud:%d == %d " % (ncloud, len(self.big_clouds))
        print "Number of register:%d" % nreg
        print "--------------------------------------"
    ###featured 7.14
    def __check_rules(self):
        ''' to make sure the every reg in cloud_reg_graph has just  1-indegree
        '''
        for reg in self.regs:
            if len(self.predecessors(reg)) > 1:
                print "Rules Error : %s %s has a predecessors more than 1" %\
                    (reg.cellref, reg.name)
                print ",".join([ str(eachPre.__class__) for eachPre in self.successors(reg)])
                #raise AssertionError
        print "Info:Check Rules of cloud_reg_graph succfully"

#------------------------------------------------------------------------------
if __name__ == '__main__':
    from circuitgraph import get_graph_from_raw_input
    g = get_graph_from_raw_input()
    cr1 = CloudRegGraph(g)
    cr1.info()