#include <random>
#include <iostream>
#include <vector>
#include <algorithm>

#define Export   extern "C" __declspec( dllexport )

// A small non-threadsafe interface for Python because neither random nor numpy match the expected RNG.
static std::mt19937 mts;
Export void seed(uint32_t seed) {
    mts.seed(seed);
}
Export uint32_t draw() {
    return mts();
}
Export uint32_t randint(uint32_t modulo) {
    std::uniform_int_distribution<unsigned int> dist{ 0,modulo - 1 };
    return dist(mts);
}
Export void shuffle(uint32_t* values, uint32_t size) {
    std::shuffle(values, values + size, mts);
}
Export uint32_t mti() {
    return mts._Idx;
}


// Main code:


struct Slot {
    char size;
    char id;  // This is the id used for matching islands. Shifted and replaced for id==3 and id==4.
    int16_t actualid;  // This is the original id.
};

struct Island {
    char id;
    char picked;
    char unwanted;
    char rivershift;
    float score;
};

struct Wanted {
    // We want to check that islands[size][index].picked is true.
    int16_t size;
    int16_t index;
};

struct IslandSelection {
    int16_t size;
    int16_t index;
};

struct World {
    Slot* slots;
    int starter;
    int npc;
    int pirate;
    int n;
};




// Mersenne Twister which becomes completely broken after n elements are drawn.
// Also, it may never be set to draw more than N-M = 227 elements.
// It is threadsafe though.
// And it does not need to process 1248 numbers to yield the first random number.
// Instead, it only ever goes up to M+nelem, and most of its iterations are not even stored in memory.
// This means roughly 450 steps for a typical map (and only ~50 stored in memory).
// Overall runtime of the seed search is 50% compared to using the std library.
// Quick estimate:
//   a) seedwork + otherwork = runtime
//   b) 0.36*seedwork + otherwork = 0.5*runtime
//   a - 2*b =>
//     seedwork - 0.72*seedwork + otherwork - 2*otherwork  = 0
//     otherwork = seedwork*(1-0.72) = 0.28*seedwork
// So with original MT, only 0.28/(1+0.28) = 22% of the time is spent outside of the RNG.
// With this Twister here, we spend 0.28/(0.36+0.28) = 44% of the time outside the RNG.
// So even this version spends most of the time on random number generation.
struct Twister {
    uint32_t mt[227];  // The Twister can never draw more than that.
    uint32_t mti;

    void set(uint32_t seed, uint32_t nelem) {
        uint32_t y;
        uint32_t m[2] = { 0, 0x9908b0df };

        // The twister basically has mt[i] = f(mt[i+M])
        // which means that we need the following elements:
        //   mt[0:nelem]
        // and
        //   mt[M:M+nelem]
        // But we store only mt[0:nelem] in memory and do the rest in registers.

        mt[0] = seed;
        for (mti = 1; mti < nelem; mti++)
            mt[mti] = 1812433253 * (mt[mti - 1] ^ (mt[mti - 1] >> 30)) + mti;


        uint32_t state = mt[mti - 1];
        for (; mti < 398; mti++)
            state = 1812433253 * (state ^ (state >> 30)) + mti;

        // Now the state corresponds to mt[M+i] and can be used
        // This code only matches the true MT if we want 227 numbers or fewer.
        // Afterwards we run past the stack.
        for (int i = 0; i < nelem; i++) {
            y = (mt[i] & 0x80000000) | (mt[i + 1] & 0x7fffffff);
            y = state ^ (y >> 1) ^ m[y & 1];

            y ^= (y >> 11);
            y ^= (y << 7) & 0x9d2c5680;
            y ^= (y << 15) & 0xefc60000;
            y ^= (y >> 18);
            mt[i] = y;

            state = 1812433253 * (state ^ (state >> 30)) + mti;
            mti += 1;
        }
        mti = 0;
    }
    uint32_t draw() {
        return mt[mti++];
    }

    uint32_t randint(int mod) {
        // Keep rejecting samples in the region around the limit until we get something lower.
        // The odds of that happening are around one in a billion though.
        uint32_t rng;
        uint32_t limit = 0xffffffff;
        if (mod < 1) return 0;
        if (limit % mod == mod - 1)
            return draw() % mod;
        while (1) {
            rng = draw();
            if (rng / mod < limit / mod)
                return rng % mod;
        }
    }

    void shuffle(Slot* start, Slot* end) {
        Slot tmp;
        uint32_t j;
        uint32_t i;
        Slot* cur;
        for (cur = start + 1, i = 1; cur < end; cur += 1, i += 1) {
            j = randint(i + 1);
            if (j != i) {
                tmp = *cur;
                *cur = start[j];
                start[j] = tmp;
            }
        }
    }

    // Like shuffle but only advances the RNG without affecting the inputs.
    void fakeshuffle(int size) {
        for (int i = 1; i < size; i++)
            randint(i + 1);
    }
};

// Fill all slots, each with a suitable island.
int fillslots(Slot* slots, int nslots, Island** islands, int* sizes, Twister* mt) {
    for (int i = 0; i < nslots; i++) {
        // Count how many islands match the slot.id.
        auto slot = slots[i];
        int sz = slot.size;
        //std::cout << "Slot: " << i << ", Slotsize: " << sz << "\n";
        auto& islandsz = islands[sz];
        // Get candidates:
        int count = 0;
        for (int j = 0; j < sizes[sz]; j++) {
            auto& island = islandsz[j];
            if (island.picked) {
                //std::cout << "Skip the picked island!\n";
                continue;
            }
            if (island.id & slot.id)
                count += 1;
        }
        //std::cout << "Candidates: " << count << "\n";
        // Draw a random number.
        int choice = mt->randint(count);
        //std::cout << "Choice: " << choice << "\n";
        // Now inform the island that it is taken.
        // Also inform the river neighbor if necessary.
        // And also abort if the island is bad.
        count = 0;
        for (int j = 0; j < sizes[sz]; j++) {
            auto& island = islandsz[j];
            if (island.picked || !(island.id & slot.id)) continue;
            // Is this the one?
            if (count == choice) {
                if (island.unwanted)
                    return 1;  // Bad end.
                island.picked = 1;
                //std::cout << "Picked island! " << island.picked << "\n";
                if (island.rivershift) {
                    //std::cout << "Rivershift " << (int) island.rivershift << "\n";
                    islandsz[j + island.rivershift].picked = 2;  // 2 means that the island was not picked, but becomes unavailable.
                }
                else {
                    //std::cout << "NO Rivershift " << (int) island.rivershift << "\n";
                }
                break;
            }
            count += 1;
        }
        // Draw the rotation!
        mt->randint(4);
    }
    return 0;  // Success! No unwanted islands placed.
}


// Test a single region (either old world or cape). Return 0 on success, else 1.
// No unwanted island may appear and all wanted islands must appear.
int testregion(int seed, int ndraws, int npcs, int pirates,
    Island** islands0, Island** islands, int* sizes,
    World world, Slot* slots,
    Wanted* wanted, int nwanted,
    float* score, float minscore) {

    // The first step is to stop as soon as a single unwanted island appears.
    // The second step comes only after all islands are picked. Then stop as soon as a wanted island does not appear.
        
    // Set up a small buffer of ndraws.
    Twister mt;
    mt.set(seed, ndraws + 3);

    // Make a copy of the original data because of picking islands and world shuffling.
    for (int i = 0; i < 3; i++) {
        memcpy(islands[i], islands0[i], sizes[i] * sizeof(Island));
    }
    memcpy(slots, world.slots, world.n * sizeof(Slot));

    // Shuffle the starters. Then starters and normals.
    mt.shuffle(slots + world.starter, slots + world.npc);
    mt.shuffle(slots, slots + world.npc);
    // Now stable sort or rather partition so that id==2 comes first.
    std::stable_partition(slots, slots + world.npc, [](Slot slot) {return slot.actualid == 1; });

    int normalstarters = world.npc;
    int res = fillslots(slots, normalstarters, islands, sizes, &mt);
    if (res) return res;  // Bad end.

    // Success! No unwanted islands so far!
    // But we still need to place NPCs and pirates.
    mt.fakeshuffle(pirates);
    mt.shuffle(slots + world.pirate, slots + world.n);

    // Now place the pirate(s) on the first slots.
    // We place as many pirates as we can until slots run out.
    int piratesplaced = std::min(world.n - world.pirate, pirates);

    // The first pirate slot(s) are now taken.
    // We emulate this by moving the untaken pirate slots to the left by the same amount.
    // This way we get a contiguous array of slots.
    // But first, draw rotation.
    for (int i = 0; i < piratesplaced; i++)
        mt.randint(4);

    // Pirate slots available after pirate selection:
    int pirateslots = world.n - world.pirate - piratesplaced;
    memmove(slots + world.pirate, slots + world.pirate + piratesplaced, pirateslots * sizeof(Slot));

    // NPCs:
    mt.fakeshuffle(npcs);
    int npcslots = world.pirate - world.npc + pirateslots;  // The slots that NPCs can choose from.
    mt.shuffle(slots + world.npc, slots + world.npc + npcslots);

    int npcsplaced = std::min(npcslots, npcs);
    // Draw rotation.
    for (int i = 0; i < npcsplaced; i++)
        mt.randint(4);

    // This time around we do not even need to move them but can just shift our starting point.
    Slot* start = slots + world.npc + npcsplaced;
    int size = npcslots - npcsplaced;

    mt.shuffle(start, start+size);
    std::stable_partition(start, start+size, [](Slot slot) {return slot.actualid == 3; });
    res = fillslots(start, size, islands, sizes, &mt);
    if (res) return res;  // Bad end.
    // NPCs done. All islands placed.



    // But are all wanted islands included?
    for (int i = 0; i < nwanted; i++) {
        //std::cout << "Check wanted" << i << "\n";
        if (islands[wanted[i].size][wanted[i].index].picked != 1)
            return 1;
        //std::cout << "Check wanted pass." << i << "\n";
    }

    //std::cout << "Picked large islands:\n";
    //for (int i = 0; i < sizes[2]; i++) {
    //    if (islands[2][i].picked == 1)
    //        std::cout << i << "\n";
    //}


    // Success again! All wanted islands included.
    // If we are not running the baseline, get the score of selected islands.

    if (score) {
        for (int sz = 0; sz < 3; sz++) {
            for (int i = 0; i < sizes[sz]; i++) {
                if (islands[sz][i].picked == 1) {
                    *score += islands[sz][i].score;
                }
            }
        }
    }
    return 0;
}






// Go through seeds from start to end and return the first seed that works.
// Each island says whether it is unwanted or not, and we stop as soon as one of them appears.
// So if there is some large island without rivers that we really do not want, we can turn it unwanted too.
// The search space (on normal difficulty) finds hits quite fast, so there is some room for filtering.
//
// If score is not null, calculate a score and filter by minscore.
Export int find(int start, uint32_t end, int stepsize, float* score,
    int ndraws, int ncapedraws, float minscore,
    int npcs, int pirate,
    Island* small, int nsmall, Island* medium, int nmedium, Island* large, int nlarge,
    Slot* slotsold, int a, int b, int c, int d, 
    Slot* slotcape, int e, int f, int g, int h,
    Wanted* wanted, int nwanted, Wanted* wantedcape, int nwantedcape) {

    World old{ slotsold, a,b,c,d };
    World cape{ slotcape, e,f,g,h };


    // Merge the islands and sizes into one, in the order small, medium, large.
    // Allocate memory to keep a copy of slots and islands.
    Island* islands0[]{ small, medium, large };
    Island* islands[3];
    int sizes[]{ nsmall, nmedium, nlarge };
    for (int i = 0; i < 3; i++)
        islands[i] = (Island*)malloc(sizes[i] * sizeof(Island));
    Slot* slots = (Slot*)malloc(std::max(old.n, cape.n) * sizeof(Slot*));

    for (uint32_t seed = start; seed < end; seed += stepsize) {
        //std::cout << seed << "\n";
        if (score) *score = 0.0;
        if (testregion(seed, ndraws, npcs + 1, pirate, islands0, islands, sizes, old, slots, wanted, nwanted, score, minscore)) continue;
        if (testregion(seed, ncapedraws, npcs, pirate, islands0, islands, sizes, cape, slots, wantedcape, nwantedcape, score, minscore)) continue;
        if (score) {
            if (*score < minscore)
                continue;
        }

        // Good end. Return the seed and score.
        for (int i = 0; i < 3; i++) free(islands[i]);
        free(slots);
        return seed;

    }

    for (int i = 0; i < 3; i++) free(islands[i]);
    free(slots);
    return -1;
}








