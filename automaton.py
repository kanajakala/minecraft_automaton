from random import randint
from numba import jit
from mcrcon import MCRcon
from tkinter import *
import numpy as np
import mcschematic
import time
import os

PALETTE1 = ['air','white_stained_glass','pink_wool','cherry_leaves','birch_wood','chiseled_quartz_block','quartz_bricks','quartz_block','white_wool','powder_snow','snow_block']
PALETTE2 = ['air','dark_oak_log','dark_oak_planks','black_terracotta','deepslate_tiles','cobbled_deepslate','deepslate_bricks','waxed_copper_block','iron_block','stripped_oak_wood']
PALETTE3 = ['air','granite','rooted_dirt','mud_bricks','packed_mud','spruce_planks','stripped_jungle_wood','stripped_oak_wood','oak_planks','waxed_exposed_copper_block','terracotta']
PALETTE4 = ['air','purple_glazed_terracotta','black_glazed_terracotta','red_nether_bricks','netherrack','stripped_mangrove_wood','warped_hyphae','blue_glazed_terracotta','warped_planks','gray_concrete','waxed_oxydised_copper']

WORLD_NAME = 'auto'
PATH = "/home/sirvp/Downloads/dev_server/plugins/FastAsyncWorldEdit/schematics"
RCON_PASSWORD = 'test'

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

@jit(nopython=True)
def neighbours_lookup(array,neighbour_type,x,y,z):
    if neighbour_type == 'M':
        return [array[z-1,y-1,x-1], array[z-1,y-1,x], array[z-1,y-1,x+1],
                      array[z-1,y,x-1], array[z-1,y,x], array[z-1,y,x+1],
                      array[z-1,y+1,x-1], array[z-1,y+1,x], array[z-1,y+1,x+1],

                      array[z,y-1,x-1], array[z,y-1,x], array[z,y-1,x+1],
                      array[z,y,x-1], array[z,y,x+1],
                      array[z,y+1,x-1], array[z,y+1,x], array[z,y+1,x+1],

                      array[z+1,y-1,x-1], array[z+1,y-1,x], array[z+1,y-1,x+1],
                      array[z+1,y,x-1], array[z+1,y,x], array[z+1,y,x+1],
                      array[z+1,y+1,x-1], array[z+1,y+1,x], array[z+1,y+1,x+1]]
    else:
        return  [array[z-1,y,x],array[z+1,y,x],
                      array[z,y-1,x],array[z,y+1,x],
                      array[z,y,x-1],array[z,y,x+1],]

@jit(nopython=True)
def count_alive(neighbours):
    n = 0
    for i in neighbours:
        if i != 0:
            n += 1
    return n

class Automaton:

    def __init__(self,x,y,z,size_x,size_y,size_z,palette):
        self.x = x
        self.y = y
        self.z = z
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z
        self.palette = palette
        self.schem = mcschematic.MCSchematic()

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
   
    def mc_gen(self,name,fade):
        for zp in range(1,self.size_z-1):
            for yp in range(1,self.size_y-1):
                for xp in range(1,self.size_x-1):
                    self.schem.setBlock((xp,yp,zp),self.palette[self.step[zp,yp,xp]%fade])
        self.schem.save(PATH,name,mcschematic.Version.JE_1_20_1)
        with MCRcon("127.0.0.1", RCON_PASSWORD) as mcr:
            resp = mcr.command(' '.join(['su load',name,WORLD_NAME,str(self.x),str(self.y),str(self.z)]))


class Regular(Automaton):

    def __init__(self,rule_string,gen_type,gen_size,weight,x,y,z,size_x,size_y,size_z,palette):
        super().__init__(x,y,z,size_x,size_y,size_z,palette)
        self.survive = [int(i) for i in rule_string.split('/')[0].split(',')]
        self.born = [int(i) for i in rule_string.split('/')[1].split(',')]
        self.fade = int(rule_string.split('/')[2])
        self.alive = [i for i in range(1,int(rule_string.split('/')[2]))]
        self.neighbour_type = rule_string.split('/')[3]
        self.gen_type = gen_type
        self.gen_size = gen_size
        self.weight = weight
        self.step = self.start(gen_type,gen_size,weight,self.fade,self.size_x,self.size_y,self.size_z)

    #numba optimizations
    @staticmethod
    @jit(nopython=True)
    def iterate(array,size_x,size_y,size_z,survive,born,fade,alive,neighbour_type):
        new = np.copy(array)
        for y in range(1, size_y-1):
            for x in range(1, size_x-1): 
                for z in range(1,size_z-1):
                    neighbours = neighbours_lookup(array,neighbour_type,x,y,z)
                    n = count_alive(neighbours) 
                    if array[z,y,x] in alive and n not in survive:
                        new[z,y,x] -= 1
                    if array[z,y,x] in alive and n in survive :
                        new[z,y,x] = array[z,y,x]
                    elif array[z,y,x] == 0 and n in born :
                        new[z,y,x] = fade-1
        return new
    
    def update(self):
        timestamp = '_regular' + str(time.time())
        self.mc_gen(timestamp,self.fade)
        self.step = self.iterate(self.step,
                                 self.size_x,self.size_y,self.size_z,
                                 self.survive,self.born,self.fade,self.alive,self.neighbour_type)
        os.remove(PATH + '/' + timestamp + '.schem')
    

class Rps(Automaton):

    def __init__(self,x,y,z,size_x,size_y,size_z,palette):
        super().__init__(x,y,z,size_x,size_y,size_z,palette)
        self.step = np.random.randint(0, 3, size=(self.size_z,self.size_y,self.size_x), dtype=np.uint8)

    #numba optimizations
    @staticmethod
    @jit(nopython=True)
    def iterate(array,size_x,size_y,size_z):
        new = np.copy(array)
        for y in range(1, size_y-1):
            for x in range(1, size_x-1): 
                for z in range(1,size_z-1):
                    neighbours = neighbours_lookup(array,'M',x,y,z)
                    if array[z,y,x] == 0 and neighbours.count(1) >= 9:
                        new[z,y,x] = 1
                    elif array[z,y,x] == 1 and neighbours.count(2) >= 9:
                        new[z,y,x] = 2
                    elif array[z,y,x] == 2 and neighbours.count(0) >= 9:
                        new[z,y,x] = 0
        return new
    
    def update(self):
        timestamp = '_rps' + str(time.time())
        self.mc_gen(timestamp,3)
        self.step = self.iterate(self.step,
                                 self.size_x,self.size_y,self.size_z)
        os.remove(PATH + '/' + timestamp + '.schem')


test = Regular(rules['clouds1'],'R',1,1,
                 0,100,0,80,80,80,
                 PALETTE1)
test_rps = Rps(85,100,0,80,80,80,PALETTE1)


while 1:
    #start_time = time.perf_counter()
    test.update()
    test_rps.update()
    #end_time = time.perf_counter()
    #print('generation time:',(end_time-start_time)*1000)

