#/usr/bin/python
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Written (W) 2009-2014 Andre Kahles, Jonas Behr, Gunnar Raetsch
# Copyright (C) 2009-2011 Max Planck Society
# Copyright (C) 2012-2014 Memorial Sloan-Kettering Cancer Center
#
# SplAdder wrapper script to start the interpreter with the correct list of arguments

import sys
import os
import scipy as sp
import cPickle


from modules import settings
from modules.core.spladdercore import spladder_core
from modules.alt_splice.collect import collect_events
from modules.alt_splice.analyze import analyze_events
from modules.count import count_graph_coverage_wrapper
import modules.init as init
import modules.rproc as rp
from modules.merge import run_merge

def parse_options(argv):

    """Parses options from the command line """

    from optparse import OptionParser, OptionGroup

    parser = OptionParser()
    required = OptionGroup(parser, 'MANDATORY')
    required.add_option('-b', '--bams', dest='bams', metavar='FILE1,FILE2,...', help='alignment files in BAM format (comma separated list)', default='-')
    required.add_option('-o', '--outdir', dest='outdir', metavar='DIR', help='output directory', default='-')
    required.add_option('-a', '--annotation', dest='annotation', metavar='FILE', help='annotation file name (annotation in *.cpickle format)', default='-')
    optional = OptionGroup(parser, 'OPTIONAL')
    optional.add_option('-l', '--logfile', dest='logfile', metavar='FILE', help='log file name [stdout]', default='-')
    optional.add_option('-u', '--user', dest='user', metavar='FILE', help='file with user settings [-]', default='-')
    optional.add_option('-F', '--spladderfile', dest='spladderfile', metavar='FILE', help='use existing SplAdder output file as input (advanced) [-]', default='-')
    optional.add_option('-c', '--confidence', dest='confidence', metavar='INT', type='int', help='confidence level (0 lowest to 3 highest) [3]', default=3)
    optional.add_option('-I', '--iterations', dest='iterations', metavar='INT', type='int', help='number of iterations to insert new introns into the graph [5]', default=5)
    optional.add_option('-M', '--merge_strat', dest='merge', metavar='<STRAT>', help='merge strategy, where <STRAT> is one of: merge_bams, merge_graphs, merge_all [merge_graphs]', default='merge_graphs')
    optional.add_option('-n', '--readlen', dest='readlen', metavar='INT', type='int', help='read length (used for automatic confidence levele settings) [36]', default=36)
    optional.add_option('-R', '--replicates', dest='replicates', metavar='R1,R2,...', help='replicate structure of files (same number as alignment files) [all R1 - no replicated]', default='-')
    optional.add_option('-L', '--label', dest='label', metavar='STRING', help='label for current experiment [-]', default='-')
    optional.add_option('-S', '--ref_strain', dest='refstrain', metavar='STRING', help='reference strain [-]', default='-')
    #optional.add_option('-', '--', dest='', metavar='', help='', default='-')
    #optional.add_option('-', '--', dest='', metavar='', help='', default='-')

    optional.add_option('-d', '--debug', dest='debug', metavar='y|n', help='use debug mode [n]', default='n')
    optional.add_option('-p', '--parallel', dest='parallel', metavar='y|n', help='use parallel implementation [n]', default='n')
    optional.add_option('-V', '--validate_sg', dest='validate_sg', metavar='y|n', help='validate splice graph [n]', default='n')
    optional.add_option('-A', '--curate_alt_prime', dest='curate_alt_prime', metavar='y|n', help='curate alt prime events [y]', default='y')
    optional.add_option('-x', '--same_genome', dest='same_genome', metavar='y|n', help='input alignments share the same genome [y]', default='y')
    optional.add_option('-i', '--insert_ir', dest='insert_ir', metavar='y|n', help='insert intron retentions [y]', default='y')
    optional.add_option('-e', '--insert_es', dest='insert_es', metavar='y|n', help='insert cassette exons [y]', default='y')
    optional.add_option('-E', '--insert_ni', dest='insert_ni', metavar='y|n', help='insert new intron edges [y]', default='y')
    optional.add_option('-r', '--remove_se', dest='remove_se', metavar='y|n', help='remove short exons [n]', default='n')
    optional.add_option('-s', '--re-infer_sg', dest='infer_sg', metavar='y|n', help='re-infer splice graph [n]', default='n')
    optional.add_option('-T', '--extract_as', dest='extract_as', metavar='y|n', help='extract alternative splicing events [y]', default='y')
    optional.add_option('-X', '--var_aware', dest='var_aware', metavar='y|n', help='alignment files are variation aware (presence of XM and XG tags) [n]', default='n')
    optional.add_option('-P', '--primary_only', dest='primary_only', metavar='y|n', help='only use primary alignments [n]', default='n')
    optional.add_option('-t', '--event_types', dest='event_types', metavar='y|n', help='list of alternative splicing events to extract [exon_skip,intron_retention,alt_3prime,alt_5prime,mult_exon_skip]', default='exon_skip,intron_retention,alt_3prime,alt_5prime,mult_exon_skip')
    optional.add_option('-C', '--truncations', dest='truncations', metavar='y|n', help='truncation detection mode [n]', default='n')
    optional.add_option('-U', '--intron_cov', dest='intron_cov', metavar='y|n', help='count intron coverage [n]', default='n')
    optional.add_option('-v', '--verbose', dest='verbose', metavar='y|n', help='verbosity', default='n')
    #optional.add_option('-', '--', dest='', metavar='y|n', help='', default=False)
    parser.add_option_group(required)
    parser.add_option_group(optional)

    (options, args) = parser.parse_args()

    if len(argv) < 2:
        parser.print_help()
        sys.exit(2)

    options.parser = parser
    return options


def spladder():

    ### get command line options
    options = parse_options(sys.argv)

    ### parse parameters from options object
    CFG = settings.parse_args(options)

    ### add dependencies provided in config section
    #if 'paths' in CFG:
    #    for i in CFG['paths']:
    #        eval('import %s'% CFG['paths'][i])

    ### load confidence level settings
    if not CFG['no_reset_conf']:
        CFG = settings.set_confidence_level(CFG)

    ### do not compute components of merged set, if result file already exists
    fn_out_merge = '' 
    prune_tag = ''
    if CFG['do_prune']:
        prune_tag = '_pruned'
    if CFG['merge_strategy'] == 'merge_graphs':
        fn_out_merge = '%s/spladder/genes_graph_conf%i.%s%s.pickle' % (CFG['out_dirname'], CFG['confidence_level'], CFG['merge_strategy'], prune_tag)


    if not 'spladder_infile' in CFG and not os.path.exists(fn_out_merge):
        ### iterate over files, if merge strategy is single
        if CFG['merge_strategy'] in ['single', 'merge_graphs']:
            idxs = range(len(CFG['samples']))
        else:
            idxs = [0]
        
        ### set parallelization
        if CFG['rproc']:
            jobinfo = []

        ### create out-directory
        if not os.path.exists(CFG['out_dirname']):
            os.makedirs(CFG['out_dirname'])

        ### create spladder sub-directory
        if not os.path.exists(os.path.join(CFG['out_dirname'], 'spladder')):
            os.makedirs(os.path.join(CFG['out_dirname'], 'spladder'))

        ### pre-process annotation, if necessary
        if CFG['anno_fname'].split('.')[-1] != 'pickle':
            if not os.path.exists(CFG['anno_fname'] + '.pickle'):
                if CFG['anno_fname'].split('.')[-1] in ['gff', 'gff3']:
                    (genes, CFG) = init.init_genes_gff3(CFG['anno_fname'], CFG, CFG['anno_fname'] + '.pickle')
                elif CFG['anno_fname'].split('.')[-1] in ['gtf']:
                    (genes, CFG) = init.init_genes_gtf(CFG['anno_fname'], CFG, CFG['anno_fname'] + '.pickle')
                else:
                    print >> sys.stderr, 'ERROR: Unknown annotation format. File needs to end in gtf or gff/gff3\nCurrent file: %s' % CFG['anno_fname']
                    sys.exit(1)
            CFG['anno_fname'] += '.pickle'

        ### add anotation contigs into lookup table
        if not 'genes' in CFG:
            genes = cPickle.load(open(CFG['anno_fname'], 'r'))
        else:
            genes = CFG['genes']
        CFG = init.append_chrms(sp.unique(sp.array([x.chr for x in genes], dtype='str')), CFG)
        del genes


        for idx in idxs:
            CFG_ = dict()
            if CFG['merge_strategy'] != 'merge_bams':
                CFG_['bam_fnames'] = CFG['bam_fnames']
                CFG_['samples'] = CFG['samples']
                CFG['bam_fnames'] = CFG['bam_fnames'][idx]
                CFG['samples'] = CFG['samples'][idx]
                CFG['out_fname'] = '%s/spladder/genes_graph_conf%i.%s.pickle' % (CFG['out_dirname'], CFG['confidence_level'], CFG['samples'])
            else:
                CFG['out_fname'] = '%s/spladder/genes_graph_conf%i.%s.pickle' % (CFG['out_dirname'], CFG['confidence_level'], CFG['merge_strategy'])

            ### assemble out filename to check if we are already done
            fn_out = CFG['out_fname']
            if CFG['do_prune']:
                fn_out = re.sub('.pickle$', '_pruned.pickle', fn_out)
            if CFG['do_gen_isoforms']:
                fn_out = re.sub('.pickle$', '_with_isoforms.pickle', fn_out)
    
            if os.path.exists(fn_out):
                print >> sys.stdout, 'All result files already exist.'
            else:
                if CFG['rproc']:
                    jobinfo.append(rp.rproc('spladder_core', CFG, 15000, CFG['options_rproc'], 40*60))
                else:
                    spladder_core(CFG)

            for key in CFG_:
                try:
                    CFG[key] = CFG_[key].copy()
                except AttributeError:
                    CFG[key] = CFG_[key]

        ### collect results after parallelization
        if CFG['rproc']:
            rp.rproc_wait(jobinfo, 30, 1.0, -1)

        ### merge parts if necessary
        if CFG['merge_strategy'] == 'merge_graphs':
            run_merge(CFG)

    ### determine count output file
    if not 'spladder_infile' in CFG:
        if CFG['validate_splicegraphs']:
            fn_in_count = '%s/spladder/genes_graph_conf%i.%s%s.validated.pickle' % (CFG['out_dirname'], CFG['confidence_level'], CFG['merge_strategy'], prune_tag)
        else:
            fn_in_count = '%s/spladder/genes_graph_conf%i.%s%s.pickle' % (CFG['out_dirname'], CFG['confidence_level'], CFG['merge_strategy'], prune_tag)
    else:
        fn_in_count = CFG['spladder_infile']
    fn_out_count = fn_in_count.replace('.pickle', '') + '.count.pickle'

    ### count segment graph
    if not os.path.exists(fn_out_count):
        count_graph_coverage_wrapper(fn_in_count, fn_out_count, CFG)

    ### count intron coverage phenotype
    if CFG['count_intron_cov']:
        fn_out_intron_count = fn_out_count.replace('mat', 'introns.pickle')
        count_intron_coverage_wrapper(fn_in_count, fn_out_intron_count, CFG)

    ### handle alternative splicing part
    if CFG['run_as_analysis']:
        collect_events(CFG)

        for idx in range(len(CFG['event_types'])):
            analyze_events(CFG, CFG['event_types'][idx])


if __name__ == "__main__":
    spladder()
