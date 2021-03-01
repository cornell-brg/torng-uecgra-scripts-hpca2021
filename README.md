Paper Artifact - Ultra-Elastic CGRAs for Irregular Loop Specialization
==========================================================================

- Authors : Christopher Torng, Peitian Pan, Yanghui Ou, Cheng Tan, and Christopher Batten
- Contact : clt67@cornell.edu, pp482@cornell.edu,
  cbatten@cornell.edu

**Abstract** - Reconfigurable accelerator fabrics, including
coarse-grain reconfigurable arrays (CGRAs), have experienced a
resurgence in interest because they allow fast-paced software
algorithm development to continue evolving post-fabrication. CGRAs
traditionally target regular workloads with data-levelparallelism
(e.g., neural networks, image processing), but once integrated into
an SoC they remain idle and unused for irregular workloads. An
emerging trend towards repurposing these idle resources raises
important questions for how to efficiently map and execute
general-purpose loops which may have irregular memory accesses,
irregular control flow, and inter-iteration loop dependencies.
Recent work has increasingly leveraged elasticity in CGRAs to
mitigate the first two challenges, but elasticity alone does not
address inter-iteration loop dependencies which can easily
bottleneck overall performance. In this paper, we address all three
challenges for irregular loop specialization and propose
ultra-elastic CGRAs (UE-CGRAs), a novel elastic CGRA that
accelerates true-dependency bottlenecks and saves energy in
irregular loops by overcoming traditional VLSI challenges. UE-CGRAs
allow configurable fine-grain dynamic voltage and frequency scaling
(DVFS) for each of potentially hundreds of tiny processing elements
(PEs) in the CGRA, enabling chains of connected PEs to “rest” at
lower voltages and frequencies to save energy, while other chains of
connected PEs can “sprint” at higher voltages and frequencies to
accelerate through true-dependency bottlenecks. UE-CGRAs rely on a
novel ratiochronous clocking scheme carefully overlaid on the
inter-PE elastic interconnect to enable low-latency crossings while
remaining fully verifiable with commercial static timing analysis
tools. We present the UE-CGRA analytical model, compiler,
architectural template, and VLSI circuitry, and we demonstrate how
UE-CGRAs can specialize for irregular loops and improve performance
(1.42–1.50×) or energy efficiency (1.24–2.32×) with reasonable area
overhead compared to traditional inelastic and elastic CGRAs, while
also improving performance (1.35–3.38×) or energy efficiency (up to
1.53×) compared to a RISC-V core.

**Artifact** - In this repository we have released our analytical
performance and energy model (used for both analytical design-space
exploration and for our compiler power-mapping pass). We have also
released a docker image with our CGRA compiler and the RTL source
code we used in the paper.

Directory Organization
--------------------------------------------------------------------------

The repository is organized as follows:

- [uecgra-analytical-model](uecgra-analytical-model)
    - This directory contains the analytical modeling described in
      **Section II** (including the discrete-event simulator and the
      energy model) as well as the compiler power-mapping pass
      described in **Section III**.

- [uecgra-docker-image](uecgra-docker-image)
    - This directory contains instructions on how to run our CGRA
      compiler and RTL simulations of our 8x8 CGRAs (inelastic,
      elastic, and ultra-elastic) on each of our kernels.


