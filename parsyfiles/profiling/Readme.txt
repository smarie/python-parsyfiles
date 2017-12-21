
# Global Profiling with pytest-profiling https://github.com/manahl/pytest-plugins/tree/master/pytest-profiling

0) you need to install http://www.graphviz.org and add its bin/ directory to the path first
1) Launch any of your pytest with --profile option. Make sure you choose the root of your project as working directory.
This will create a prof/ dir.
2) execute the two following commands to generate the synthesis svg file:

    gprof2dot -f pstats prof/combined.prof > prof/tmp
    dot -Tsvg -o prof/combined.svg prof/tmp



# More precise profiling

- first conda/pip install line_profiler
- then kernprof -v -l exec_on_test_by_type.py
- later view :
    * python -m line_profiler exec_on_test_by_type.py.lprof ([> log] for text output)





source : https://github.com/rkern/line_profiler
and : https://github.com/fabianp/memory_profiler


