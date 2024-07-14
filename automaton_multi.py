
from random import randint
from numba import njit, prange
from mcrcon import MCRcon
import numpy as np
import mcschematic
from rcon.source import Client
import time
import os
import concurrent.futures
import sys
from functools import partial
import threading


PALETTE1 = np.array(['air', 'white_stained_glass', 'pink_wool', 'cherry_leaves', 'birch_wood', 'chiseled_quartz_block', 'quartz_bricks', 'quartz_block', 'white_wool', 'powder_snow', 'snow_block'])
PALETTE2 = np.array(['air', 'dark_oak_log', 'dark_oak_planks', 'black_terracotta', 'deepslate_tiles', 'cobbled_deepslate', 'deepslate_bricks', 'waxed_copper_block', 'iron_block', 'stripped_oak_wood'])
PALETTE3 = np.array(['air', 'granite', 'rooted_dirt', 'mud_bricks', 'packed_mud', 'spruce_planks', 'stripped_jungle_wood', 'stripped_oak_wood', 'oak_planks', 'waxed_exposed_copper_block', 'terracotta'])
PALETTE4 = np.array(['air', 'pearlescent_froglight', 'black_glazed_terracotta', 'white_concrete', 'iron_block', 'stripped_mangrove_wood', 'warped_hyphae', 'blue_glazed_terracotta', 'warped_planks', 'gray_concrete', 'waxed_oxydised_copper'])


WORLD_NAME = 'world'
PATH = "/home/sirvp/Downloads/dev_server/plugins/FastAsyncWorldEdit/schematics"
RCON_PASSWORD = 'test'

rules = {
    'clouds': '13,14,15,16,17,18,19,20,21,22,23,24,25,26/13,14,17,18,19/2/M',
    'clouds1': '12,13,14,15,16,17,18,19,20,21,22,23,24,25,26/13,14/2/M',
    'cube': '3/1,2,3/10/M',
    'cube1': '4,5/1,2/10/M',
    'architecture': '4,5,6/3/2/M',
    'construction': '0,1,2,4,6,7,8,9,10,11,13,14,15,16,17,21,22,23,24,25,26/9,10,16,23,24/2/M',
    'builder': '1,2,3/1,4,5/5/N',
    'coral': '5,6,7,8/6,7,9,12/4/M'
}

@njit(cache=True)
def neighbours_lookup(array, neighbour_type, x, y, z):
    if neighbour_type == 'M':
        return array[z-1:z+2, y-1:y+2, x-1:x+2].ravel()
    elif neighbour_type == 'Simple':
        return np.array([
            array[z,y,x], array[z-1,y,x], array[z+1,y,x],
            array[z,y-1,x], array[z,y+1,x],
            array[z,y,x-1], array[z,y,x+1]
        ])
    else:
        return np.array([
            array[z-1,y,x], array[z+1,y,x],
            array[z,y-1,x], array[z,y+1,x],
            array[z,y,x-1], array[z,y,x+1]
        ])

@njit(cache=True)
def count_alive(neighbours):
    return np.sum(neighbours != 0)

def generate_minecraft_schematic_chunk(chunk, palette, start_z):
    schem_chunk = mcschematic.MCSchematic()
    for z in range(chunk.shape[0]):
        for y in range(chunk.shape[1]):
            for x in range(chunk.shape[2]):
                state = chunk[z, y, x]
                if state > 0:
                    block = palette[state % len(palette)]
                    schem_chunk.setBlock((x, y, z), block)
    return schem_chunk

def generate_minecraft_schematics(cellular_automaton_state, palette, num_chunks=8):
    # Split the cellular automaton state into chunks along the z-axis
    chunk_size = cellular_automaton_state.shape[0] // num_chunks
    chunks = [cellular_automaton_state[i:i+chunk_size] for i in range(0, cellular_automaton_state.shape[0], chunk_size)]
    
    # Create a partial function with fixed palette
    generate_chunk = partial(generate_minecraft_schematic_chunk, palette=palette)
    
    schematics = []
    
    # Use a ThreadPoolExecutor to process chunks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_chunks) as executor:
        future_to_chunk = {executor.submit(generate_chunk, chunk, start_z=i*chunk_size): i 
                           for i, chunk in enumerate(chunks)}
        
        for future in concurrent.futures.as_completed(future_to_chunk):
            chunk_index = future_to_chunk[future]
            try:
                chunk_schem = future.result()
                schematics.append((chunk_index, chunk_schem))
                print(f'\rChunk {chunk_index} completed successfully',end="\r",flush=True)
            except Exception as exc:
                print(f'Chunk {chunk_index} generated an exception: {exc}')

    # Sort schematics by chunk index
    schematics.sort(key=lambda x: x[0])
    return [schem for _, schem in schematics]



class Automaton:
    def __init__(self, x, y, z, size_x, size_y, size_z, palette):
        self.x = x
        self.y = y
        self.z = z
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z
        self.palette = palette
        self.schem = None  # Initialize later

    def start(self, gen_type, n, weight, fade, size_x, size_y, size_z):
        step = np.zeros((size_z, size_y, size_x))
        
        if gen_type == 'R':
            step = np.random.randint(0, fade, size=(size_z, size_y, size_x))
        elif gen_type in ['P', 'C']:
            center_z, center_y, center_x = size_z // 2, size_y // 2, size_x // 2
            half_n = n // 2
            mask = np.random.random((n, n, n)) < weight if gen_type == 'C' else np.ones((n, n, n))
            step[center_z-half_n:center_z+half_n, center_y-half_n:center_y+half_n, center_x-half_n:center_x+half_n][mask] = fade - 1
        elif gen_type == 'S':
            for _ in range(n):
                z, y, x = np.random.randint(1, size_z - weight - 1, 3)
                step[z:z+weight, y:y+weight, x:x+weight] = fade - 1
        elif gen_type == 'T':
            center_z, center_y, center_x = size_z // 2, size_y // 2, size_x // 2
            mask = np.random.random((n, n)) < weight
            step[center_z:center_z+n, center_y, center_x:center_x+n][mask] = fade - 1
        
        return step


    def mc_gen(self, cellular_automaton_state):
        schematics = generate_minecraft_schematics(cellular_automaton_state, self.palette)
        
        chunk_size_z = self.size_z // 8
        
        for i, schematic in enumerate(schematics):
            schematic_name = f"schematic_chunk_{i}"
            schematic.save(PATH, schematic_name, mcschematic.Version.JE_1_20_1)
            
            # Calculate the z-offset for this chunk
            z_offset = i * chunk_size_z
            
            # Load the schematic into Minecraft
            try:
                
                with Client('127.0.0.1', 25575, passwd='test') as client:
                    response = client.run(f'su load {schematic_name} {WORLD_NAME} {self.x} {self.y} {self.z + z_offset}')
                    print('\rserver response:'+response,end='\r',flush=True)
            except Exception as exc:
                print(f"error with Mcrcon: {exc}")


class Regular(Automaton):
    def __init__(self, rule_string, gen_type, gen_size, weight, x, y, z, size_x, size_y, size_z, palette):
        super().__init__(x, y, z, size_x, size_y, size_z, palette)
        rule_parts = rule_string.split('/')
        self.survive = np.array([int(i) for i in rule_parts[0].split(',')])
        self.born = np.array([int(i) for i in rule_parts[1].split(',')],)
        self.fade = int(rule_parts[2])
        self.alive = np.arange(1, self.fade)
        self.neighbour_type = rule_parts[3]
        self.gen_type = gen_type
        self.gen_size = gen_size
        self.weight = weight
        self.step = self.start(gen_type, gen_size, weight, self.fade, self.size_x, self.size_y, self.size_z)

    @staticmethod
    @njit(parallel=True, cache=True)
    def iterate(array, size_x, size_y, size_z, survive, born, fade, alive, neighbour_type):
        new = np.copy(array)
        for y in prange(1, size_y - 1):
            for x in prange(1, size_x - 1):
                for z in prange(1, size_z - 1):
                    neighbours = neighbours_lookup(array, neighbour_type, x, y, z)
                    n = count_alive(neighbours)
                    if array[z, y, x] in alive:
                        if n not in survive:
                            new[z, y, x] = max(0, array[z, y, x] - 1)
                    elif array[z, y, x] == 0 and n in born:
                        new[z, y, x] = fade - 1
        return new


class Rps(Automaton):
    def __init__(self, x, y, z, size_x, size_y, size_z, palette):
        super().__init__(x, y, z, size_x, size_y, size_z, palette)
        self.step = np.random.randint(0, 3, size=(self.size_z, self.size_y, self.size_x))

    @staticmethod
    @njit(parallel=True, cache=True)
    def iterate(array, size_x, size_y, size_z):
        new = np.copy(array)
        for y in prange(1, size_y - 1):
            for x in prange(1, size_x - 1):
                for z in prange(1, size_z - 1):
                    neighbours = neighbours_lookup(array, 'M', x, y, z)
                    if array[z, y, x] == 0 and np.sum(neighbours == 1) >= 9:
                        new[z, y, x] = 1
                    elif array[z, y, x] == 1 and np.sum(neighbours == 2) >= 9:
                        new[z, y, x] = 2
                    elif array[z, y, x] == 2 and np.sum(neighbours == 0) >= 9:
                        new[z, y, x] = 0
        return new


def update_automaton(automaton, iterations):
    for i in range(iterations):
        if isinstance(automaton, Regular):
            automaton.step = Regular.iterate(automaton.step, automaton.size_x, automaton.size_y, automaton.size_z, 
                                             automaton.survive, automaton.born, automaton.fade, automaton.alive, automaton.neighbour_type)
        elif isinstance(automaton, Rps):
            automaton.step = Rps.iterate(automaton.step, automaton.size_x, automaton.size_y, automaton.size_z)
        elif isinstance(automaton, Simple):
            automaton.step = Simple.iterate(automaton.step, automaton.alive, automaton.size_x, automaton.size_y, automaton.size_z)

    #timestamp = f'_{automaton.__class__.__name__.lower()}_{time.time()}_{i}'
    automaton.mc_gen(automaton.step)

def update_automaton_wrapper(automaton, iterations):
    return update_automaton(automaton, iterations)

def main():
    #regular = Regular(rules['builder'], 'P', 4, 1, 0, 100, 0, 50, 50, 50, PALETTE4)
    #rps = Rps(52, 100, 0, 200, 200, 200, PALETTE1)
    #simple = Simple(14, 104, 100, 0, 50, 50, 50, PALETTE1)

    automatons = [Rps(-100, 200, 0, 200, 200, 200, PALETTE1)
                  ]

    if len(sys.argv) == 1 or sys.argv[1] == "continuous":
        while True:
            start_time = time.perf_counter()
            with concurrent.futures.ProcessPoolExecutor() as executor:
                list(executor.map(update_automaton_wrapper, automatons, [1]*len(automatons)))
            end_time = time.perf_counter()
            print(f'\rGeneration time: {(end_time - start_time):.3f}s', flush=True, end='')
    elif sys.argv[1] == "generate":
        start_time = time.perf_counter()
        step_number = 100 if len(sys.argv) == 2 else int(sys.argv[2])
        with concurrent.futures.ProcessPoolExecutor() as executor:
            list(executor.map(update_automaton_wrapper, automatons, [step_number]*len(automatons)))
        end_time = time.perf_counter()
        print(f'Generation time: {(end_time - start_time):.3f}s')

if __name__ == "__main__":
    main()

