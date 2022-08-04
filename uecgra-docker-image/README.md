Ultra-Elastic CGRA Docker Image
==========================================================================

This directory contains the instructions for running CGRA compiler pass
and RTL simulation described in the paper.

## CGRA compiler
  - We were unable to build LLVM binaries into the docker image due to excessive disk space usage.
  - If you'd like to try our compiler flow (implemented as an LLVM pass), please make sure you have LLVM tools installed to your $PATH (we used version 8.0)
  - To build the LLVM pass:
    - cd /artifact_top/uecgra/llvm-pass-cgra
    - mkdir build
    - cd build
    - cmake ..
    - make -j12
    - cd /artifact_top/uecgra/benchmark/[kernel-name]
    - ./compile.sh
    - ./run.sh
  - [kernel-name] is one of the following targets
    - adpcm, blowfish, dither, fft, fir, latnrm, susan
  - The output of the LLVM pass is a CGRA configuration json file (can be used in RTL simulation). Please note that you might need to tweak the json output in order to correctly map the configuration onto our CGRA.

## CGRA RTL simulation using provided docker image
  - First, you need to download the pre-built docker image `torng-uecgra-hpca2021.tar.gz`
    - Download from https://doi.org/10.5281/zenodo.4589143 [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4589143.svg)](https://doi.org/10.5281/zenodo.4589143)
  - Then you need the following two commands to run a docker container
    - docker load --input torng-uecgra-hpca2021.tar.gz
    - docker run -it --cap-add SYS_ADMIN uecgra-src /bin/bash
  - Once you are inside the image, source the bashrc script:
    - source /root/.bashrc

### Running Elastic CGRA tests
  - Make sure you are inside the docker image and have sourced /root/.bashrc
    - workon ecgra
    - cd /artifact_top/uecgra
    - mkdir -p build-ecgra
    - cd build-ecgra
    - pytest ../src/cgra/test/StaticCGRA_test.py::StaticCGRA_Trans_Tests::test_[test-name] -vs --tb=short --clock-time=5.0
    - deactivate
  - [test-name] is of the following targets
    - llist, dither, susan, fft, bf
  - Each test generates a synthesizable RTL source file, performance stats, and a waveform which can be used to drive our energy analysis flow
  - Make sure you have deactivated the current virtual environment (ecgra) before you try UE-CGRA or processor tests!

### Running Ultra-Elastic CGRA tests
  - Make sure you are inside the docker image and have sourced /root/.bashrc
    - workon uecgra
    - cd /artifact_top/uecgra
    - mkdir -p build-uecgra
    - cd build-uecgra
    - pytest ../src/cgra/test/StaticCGRA_RGALS_test.py -vs --tb=short -k [test-name].json --clock-time=5.0
    - deactivate
  - [test-name] is of format [kernel-name][suffix]
    - [kernel-name] is one of the following targets
      - llist, dither, susan, fft, bf
    - [suffix] is one of the following targets
      - [empty]: no suffix -- run the test with all PEs and SRAMs at canonical voltage and frequency
      - _dvfs: performance-optimized configuration; run the test with a configuration that is optimized for better throughput
      - _dvfs_eeff: energy-optimized configuration; run the test with a configuration that is optimized for better energy efficiency
  - Example:
    - `-k fir.json`: run the FIR kernel with all PEs and SRAMs at canonical VF
    - `-k dither_dvfs.json`: run the dither kernel with a performance-optimized configuration
    - `-k llist_dvfs_eeff.json`: run the llist kernel with an energy-optimized configuration
  - Each test generates a synthesizable RTL source file, performance stats, and a waveform which can be used to drive our energy analysis flow
  - Make sure you have deactivated the current virtual environment (uecgra) before you try E-CGRA or processor tests!

### Running RISCV processor tests
  - The docker image also includes the pre-compiled binaries of the kernels used in this paper
  - Make sure you are inside the docker image and have sourced /root/.bashrc
    - workon proc
    - cd /artifact_top/uecgra
    - mkdir -p build-proc
    - cd build-proc
    - ../proc-sim/mcore-sim-elf --ncores 1 --single-cycle-mul --stats ../app/build-riscv/cgra_ubmark-[test-name]
  - [test-name] is one of the following targets
    - bf, fft, fir, latnrm, susan, dither, llist
  - Each test generates a synthesizable RTL source file, performance stats, and a waveform which can be used to drive our energy analysis flow
  - Make sure you have deactivated the current virtual environment (proc) before you try E-CGRA or UE-CGRA tests!

### Expected System Efficiency

The docker image does not contain any technology-specific
information or backend physical design scripts due to our NDAs.
However, if you are able to source your own backend physical design
tools and scripts, we provide numbers for the system efficiency you
should expect.

We provide our system efficiency numbers for FFT in GOPS/W, along
with our assumptions and caveats. We have chosen not to include the
host system and main memory in our calculation, so please keep
this in mind.

For reference, here is the DFG for FFT with 28 operations and the
critical sequence of DFG nodes highlighted in red:

![](dfg-fft.jpg)

**System Efficiency for FFT (array only)**

- Performance -- 1.75 GOPS
    - FFT inner loop iterates and executes a total of 28000 ops
    - Execution time is 15980e-9 seconds
    - Performance is 28000/15980e-9 = 1.75 GOPS
    - OP definition
        - All LLVM primitives that can be mapped to an elastic PE
        - E.g., load, store, add, mul, branch, equality, phi

- Power -- 16.71 mW
    - Breakdown
        - PEs and their local clock networks -- 14.01 mW (83.8%)
        - SRAMs -- 1.78 mW (10.7%)
        - Global clock network -- 0.86 mW (5.1%)
        - Total -- 16.71 mW

- Operating Conditions
    - TSMC 28nm, 0.9V, SVT only (no HVT/LVT/ULVT), all typical corner

- Final System Efficiency (all operations) -- 104.9 GOPS/W
    - 1.75 GOPS / 16.71 mW = 104.9 GOPS/W

- Final System Efficiency (core operations only) -- 37.5 GOPS/W
    - Core operations definition
        - These are the core arithmetic operations that would count towards FLOPS
        - In the FFT DFG, there are ten core operations after the four loads that execute per inner loop iteration (4 multiplies, 3 add, 3 sub).
        - Therefore the final system efficiency will be 10/28ths of the GOPS/W (all operations).
    - 10 core ops / 28 total ops * 104.9 GOPS/W = 37.5 GOPS/W

- Caveats
    - No PE power gating was done with FFT, because almost all PEs were needed for routing (63/64 PEs)
    - No hierarchical clock gating was done either, for the same reason
    - No DVFS mechanisms at play at all (no ultra elastic)
    - 32-bit datapath
    - All numbers are post-pnr
    - Array is 44% utilized (28/64 PEs)
        - Unrolling to utilize the remaining PEs is not expected to change the GOPS/W much (beyond a few percent)
    - Does NOT include main memory or the host core, and data is assumed preloaded into SRAMs
    - **Eager fork caveat** -- The throughput of FFT on our RTL is 12 cycles/iteration (1.75 GOPS). However, the throughput of FFT on the UE-CGRA analytical model is 4 cycles/iteration, which makes more sense because there are four nodes in the critical DFG cycle (5.25 GOPS). The discrepancy arises because our analytical model assumes support for eager forks as described in "Elastic CGRAs" FPGA 2013 [21], but our RTL does not yet support this feature, leading to a mismatch. We expect that RTL support for eager forking will recover this unintended performance loss. Note that this mismatch has minimal impact on the GOPS/W, since performance and power would both increase by a factor of three. Also note that the conclusions of the paper do not change.



