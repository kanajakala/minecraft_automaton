from random import randint
from numba import jit
from mcrcon import MCRcon
from tkinter import *
import numpy as np
import mcschematic
import time
import os

PALETTE1 = ['air','pink_concrete','pink_wool','cherry_leaves','birch_wood','chiseled_quartz_block','quartz_bricks','quartz_block','white_wool','powder_snow','snow_block']
PALETTE2 = ['air','dark_oak_log','dark_oak_planks','black_terracotta','deepslate_tiles','cobbled_deepslate','deepslate_bricks','waxed_copper_block','iron_block','stripped_oak_wood']

WORLD_NAME = 'auto'
PATH = "/home/sirvp/Downloads/dev_server/plugins/FastAsyncWorldEdit/schematics"

rules = {
    'clouds': '13,14,15,16,17,18,19,20,21,22,23,24,25,26/13,14,17,18,19/2/M',
    'clouds1': '12,13,14,15,16,17,18,19,20,21,22,23,24,25,26/13,14/2/M',
    'cube': '3/1,2,3/10/M',
    'cube1': '4,5/1,2/10/M',
    'architecture': '4,5,6/3/2/M',
    'construction': '0,1,2,4,6,7,8,9,10,11,13,14,15,16,17,21,22,23,24,25,26/9,10,16,23,24/2/M',
    'builder1': '1,2,3/1,4,5/5/N',
    'coral': '5,6,7,8/6,7,9,12/4/M'
}

class Automaton:

    def __init__(self,rule_string,gen_type,gen_size,weight,x,y,z,size_x,size_y,size_z,palette,path,world_name):
        self.survive = [int(i) for i in rule_string.split('/')[0].split(',')]
        self.born = [int(i) for i in rule_string.split('/')[1].split(',')]
        self.fade = int(rule_string.split('/')[2])
        self.alive = [i for i in range(1,int(rule_string.split('/')[2]))]
        self.neighbour_type = rule_string.split('/')[3]
        self.schem = mcschematic.MCSchematic()
        self.palette = palette
        self.gen_type = gen_type
        self.gen_size = gen_size
        self.weight = weight
        self.x = x
        self.y = y
        self.z = z
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z
        self.path = path
        self.world_name = world_name
        self.step = self.start(gen_type,gen_size,weight,self.fade,self.size_x,self.size_y,self.size_z)

    #numba optimizations
    @staticmethod
    @jit(nopython=True)
    def _iterate(array,size_x,size_y,size_z,survive,born,fade,alive,neighbour_type):
        new = np.copy(array)
        for y in range(1, size_y-1):
            for x in range(1, size_x-1): 
                for z in range(1,size_z-1):
                    if neighbour_type == 'M':
                        neighbours = [array[z-1,y-1,x-1], array[z-1,y-1,x], array[z-1,y-1,x+1],
                                      array[z-1,y,x-1], array[z-1,y,x], array[z-1,y,x+1],
                                      array[z-1,y+1,x-1], array[z-1,y+1,x], array[z-1,y+1,x+1],

                                      array[z,y-1,x-1], array[z,y-1,x], array[z,y-1,x+1],
                                      array[z,y,x-1], array[z,y,x+1],
                                      array[z,y+1,x-1], array[z,y+1,x], array[z,y+1,x+1],

                                      array[z+1,y-1,x-1], array[z+1,y-1,x], array[z+1,y-1,x+1],
                                      array[z+1,y,x-1], array[z+1,y,x], array[z+1,y,x+1],
                                      array[z+1,y+1,x-1], array[z+1,y+1,x], array[z+1,y+1,x+1]]
                    else:
                        neighbours = [array[z-1,y,x],array[z+1,y,x],
                                      array[z,y-1,x],array[z,y+1,x],
                                      array[z,y,x-1],array[z,y,x+1],]
                    n = 0 
                    for i in neighbours:
                        if i != 0:
                            n += 1

                    if array[z,y,x] in alive and n not in survive:
                        new[z,y,x] -= 1
                    if array[z,y,x] in alive and n in survive :
                        new[z,y,x] = array[z,y,x]
                    elif array[z,y,x] == 0 and n in born :
                        new[z,y,x] = fade-1
        return new

    def start(self,gen_type,n,weight,fade,size_x,size_y,size_z):
        def gen_full(n,weight):
            step = np.full((size_z,size_y,size_x),0)
            for i in range(n):
                for j in range(n):
                    for k in range(n):
                        if randint(0,99) < weight*100:
                            step[((size_z//2)-(n//2))+i,((size_y//2)-(n//2))+j,((size_x//2)-(n//2))+k] = fade-1
            return step
        if gen_type == 'R':
            step = np.random.randint(0, fade, size=(size_z,size_y,size_x))
        elif gen_type == 'P':
            step = gen_full(n,1)
        elif gen_type == 'S':
            step = np.full((size_z,size_y,size_x),0)
            for r in range(n):
                z = randint(1,size_z-(weight+1))
                y = randint(1,size_y-(weight+1))
                x = randint(1,size_x-(weight+1))
                for i in range(weight):
                    for j in range(weight):
                        for k in range(weight): 
                            step[z+i,y+j,x+k] = fade-1
        elif gen_type == 'C':
            step = gen_full(n,weight)
        elif gen_type == 'T':
            step = np.full((size_z,size_y,size_x),0)
            for j in range(n):
                for k in range(n):
                    if randint(0,99) < weight*100:
                        step[(size_z//2)+j,(size_y//2),(size_x//2)+k] = fade-1
        else:
            print('invalid gen_type, last rule must be R (random), P (point in the center), S (scattered points), C (point in the center but with random holes), T (plate of size n)')
        
        return step
   
    #wrapper function to work with numba
    def iterate(self):
        return self._iterate(self.step,
                             self.size_x,self.size_y,self.size_z,
                             self.survive,self.born,self.fade,self.alive,self.neighbour_type)

    def mc_gen(self,name):
        for zp in range(1,self.size_z-1):
            for yp in range(1,self.size_y-1):
                for xp in range(1,self.size_x-1):
                    self.schem.setBlock((xp,yp,zp),self.palette[self.step[zp,yp,xp]%self.fade])
        self.schem.save(self.path,name,mcschematic.Version.JE_1_20_1)
        with MCRcon("127.0.0.1", 'test') as mcr:
            resp = mcr.command(' '.join(['su load',name,self.world_name,str(self.x),str(self.y),str(self.z)]))

    def update(self):
        timestamp = str(time.time())
        self.mc_gen(timestamp)
        self.step = self.iterate()
        os.remove(self.path + '/' + timestamp + '.schem')

test = Automaton(rules['cube1'],'P',4,1,
                 0,100,0,80,80,80,
                 PALETTE2,PATH,WORLD_NAME)

while 1:
    #start_time = time.perf_counter()
    test.update()
    #end_time = time.perf_counter()
    #print('generation time:',(end_time-start_time)*1000)

