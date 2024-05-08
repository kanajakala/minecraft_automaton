from random import randint
from numba import jit
from numba.experimental import jitclass
from mcrcon import MCRcon
from tkinter import *
import numpy as np
import mcschematic
import time
import os

PALETTE1 = ['air','white_stained_glass','pink_wool']
PALETTE2 = ['air','dark_oak_log','dark_oak_planks']

WORLD_NAME = 'auto'
PATH = "/home/sirvp/Downloads/dev_server/plugins/FastAsyncWorldEdit/schematics"

class Automaton:
    def __init__(self,x,y,z,size_x,size_y,size_z,palette,path,world_name):
        self.palette = palette
        self.x = x
        self.y = y
        self.z = z
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z
        self.path = path
        self.world_name = world_name
        self.step = np.random.randint(0, 3, size=(self.size_z,self.size_y,self.size_x), dtype=np.uint8)

    schem = mcschematic.MCSchematic()
    
    #numba optimizations
    @staticmethod
    @jit(nopython=True,fastmath=True)
    def _iterate(array,size_x,size_y,size_z):
        new = np.copy(array)
        for y in range(1, size_y-1):
            for x in range(1, size_x-1): 
                for z in range(1,size_z-1):
                    neighbours = [array[z-1,y-1,x-1], array[z-1,y-1,x], array[z-1,y-1,x+1],
                                  array[z-1,y,x-1], array[z-1,y,x], array[z-1,y,x+1],
                                  array[z-1,y+1,x-1], array[z-1,y+1,x], array[z-1,y+1,x+1],

                                  array[z,y-1,x-1], array[z,y-1,x], array[z,y-1,x+1],
                                  array[z,y,x-1], array[z,y,x+1],
                                  array[z,y+1,x-1], array[z,y+1,x], array[z,y+1,x+1],

                                  array[z+1,y-1,x-1], array[z+1,y-1,x], array[z+1,y-1,x+1],
                                  array[z+1,y,x-1], array[z+1,y,x], array[z+1,y,x+1],
                                  array[z+1,y+1,x-1], array[z+1,y+1,x], array[z+1,y+1,x+1]]

                    n = 0 
                    for i in neighbours:
                        if i != 0:
                            n += 1

                    if array[z,y,x] == 0 and neighbours.count(1) >= 9:
                        new[z,y,x] = 1
                    elif array[z,y,x] == 1 and neighbours.count(2) >= 9:
                        new[z,y,x] = 2
                    elif array[z,y,x] == 2 and neighbours.count(0) >= 9:
                        new[z,y,x] = 0
        return new

    #wrapper function to work with numba
    def iterate(self):
        return self._iterate(self.step,self.size_x,self.size_y,self.size_z)

    def mc_gen(self,name):
        for zp in range(1,self.size_z-1):
            for yp in range(1,self.size_y-1):
                for xp in range(1,self.size_x-1):
                    self.schem.setBlock((xp,yp,zp),self.palette[self.step[zp,yp,xp]])
        self.schem.save(self.path,name,mcschematic.Version.JE_1_20_1)
        with MCRcon("127.0.0.1", 'test') as mcr:
            resp = mcr.command(' '.join(['su load',name,self.world_name,str(self.x),str(self.y),str(self.z)]))

    def update(self):
        timestamp = str(time.time())
        self.mc_gen(timestamp)
        self.step = self.iterate()
        os.remove(self.path + '/' + timestamp + '.schem')


test = Automaton(0,100,0,50,50,4,PALETTE1,PATH,WORLD_NAME) 

while 1:
    #start_time = time.perf_counter()
    test.update()
    #end_time = time.perf_counter()
    #print('generation time:',(end_time-start_time)*1000)

