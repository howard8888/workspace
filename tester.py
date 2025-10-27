


from cca8_world_graph import WorldGraph

g = WorldGraph()
now = g.ensure_anchor("NOW") #bi
print(now)
print(g.plan_pretty(now, "posture:standing"))# expect '(no path)'
b = g.add_predicate("posture:standing", attach="NOW")  # auto edge: NOW -> b2
print(g.plan_pretty(now, "posture:standing"))          # b1(NOW) --then--> b2[posture:standing]

#create two predicate nodes without auto-linking

a = g.add_predicate("posture:fallen", attach="none")
b = g.add_predicate("posture:standing", attach="none")
print('two nodes created a and b: ', a,b) #b3 b4

#manually add an edge a --> b with an action label
g.add_edge(a,b, label="stand")

print(g.plan_pretty(a, "posture:standing")) #b3[posture:fallen] --stand--> b4[posture:standing]

#try to add an edge automatically so a new predicate/cue binding will automatically have a linking
#  from the previous nodes

c = g.add_predicate("posture:jumping", attach="latest")
print('node c created: ', c)
print(g.plan_pretty(a, "posture:jumping"))
