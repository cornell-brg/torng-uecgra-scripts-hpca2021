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
    - Download from https://doi.org/10.5281/zenodo.4568992
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
