import cProfile
import pstats
profiler = cProfile.Profile()
profiler.enable()

from app import app


profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime').print_stats(30)  # Print top 20 by cumulative time