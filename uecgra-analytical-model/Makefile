#=========================================================================
# Makefile
#=========================================================================
# The targets here are used for merging PDFs into a "flip book" view of
# tokens propagating through a DFG when the argument "do_plot=True" is
# given to the Simulator.
#
# Author : Christopher Torng
# Date   : February 28, 2021

r ?= r0

%.pdf : %.dot
	dot -Tpdf $< > $@

dots = $(wildcard *.$(r).dot)
pdfs = $(dots:.dot=.pdf)

merged.pdf: $(pdfs)
	( sorted_pdfs=$$(ls -1 $(pdfs) | sort -n | tr '\n' ' '); \
		gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -dPDFSETTINGS=/prepress \
		  -sOutputFile=merged.pdf $$sorted_pdfs; )

clean:
	rm -f *.pdf *.dot *.pyc

