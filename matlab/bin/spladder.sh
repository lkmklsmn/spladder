#/bin/bash
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Written (W) 2009-2013 Andre Kahles, Jonas Behr, Gunnar Raetsch
# Copyright (C) 2009-2011 Max Planck Society
# Copyright (C) 2012-2013 Memorial Sloan-Kettering Cancer Center
#
# SplAdder wrapper script to start the interpreter with the correct list of arguments

set -e

function usage () {
    echo "
    
    Usage: SplAdder [-OPTION VALUE] 

    Options (default values in [...]):

    MANDATORY:
    -b  FILE1,FILE2,...     alignment files in BAM format (comma separated list)
    -o  DIR                 output directory
    -a  FILE                annotation file name (annotation in *.mat|*.gff format)

    GENERAL:
    -l  FILE                log file name [stdout]
    -v  y|n                 use verbose output mode [n]
    -d  y|n                 use debug mode [n]
    -p  y|n                 use parallel engine [n]

    INPUT FILTERING:
    -c  INT                 confidence level (0 lowest to 3 highest) [3]
    -O  y|n                 annotation is in half-open coordinates [n]
    -P  y|n                 only use primary alignments from provided files [n]
    -X  y|n                 alignment files are variation aware (presence of XM and XG tags) [n]
    -n  INT                 read length (used for automatic confidence levele settings) [36]

    GRAPH AUGMENTATION:
    -M  <STRAT>             merge strategy, where <STRAT> is one on:
                            merge_bams, merge_graphs, merge_all [merge_graphs]
    -x  y|n                 input alignments share the same genome [y]
    -i  y|n                 insert intron retentions [y]
    -e  y|n                 insert cassette exons [y]
    -E  y|n                 insert new intron edges [y]
    -I  INT                 number of iterations to insert new introns
                            into the graph [5]
    -r  y|n                 remove short exons [n]
    -V  y|n                 validate splice graph [n]

    EVENT EXTRACTION:
    -T  y|n                 extract alternative splicing events [y]
    -t  STRING,STRING,...   list of alternative splicing events to extract 
                            [exon_skip,intron_retention,alt_3prime,alt_5prime,mult_exon_skip]
    -A  y|n                 curate alt prime events [y]
    -F  FILE                use existing SplAdder output file as input (advanced) [-]

    ADVANCED/EXPERIMENTAL:
    -C  y|n                 truncation detection mode [n] (experimental)
    -U  y|n                 count intron coverage [n] (experimental)
    -R  R1,R2,...           replicate structure of files (same number as
                            alignment files) [all R1 - no replicated] (experimental)
    -s  y|n                 re-infer splice graph [n]
    -L  STRING              label for current experiment [-]
    -S  STRING              reference strain [-]
    "

    exit 0
}

[[ -z "$1" ]] && usage

### who am I and where am I running?
PROG=`basename $0`
DIR=`dirname $0`

. ${DIR}/spladder_config.sh

### mandatory parameters
S_BAM_FNAME=""
S_ANNO_FNAME=""
S_OUT_DIRNAME=""

### parse parameters from command lines
while getopts "b:o:l:a:u:c:I:M:R:L:S:d:p:V:O:v:A:x:i:e:E:r:s:T:t:n:F:X:P:C:U:h" opt
do
    case $opt in
    b ) S_BAM_FNAME="$OPTARG" ;;
    o ) S_OUT_DIRNAME="$OPTARG" ;;
    l ) S_LOG_FNAME="$OPTARG" ;;
    a ) S_ANNO_FNAME="$OPTARG" ;;
    u ) S_USER_FNAME="$OPTARG" ;;
    c ) I_CONFIDENCE="$OPTARG" ;;
    I ) I_INSERT_INTRON_ITER="$OPTARG" ;;
    M ) S_MERGE_STRATEGY="$OPTARG" ;;
    R ) S_REPLICATE_IDX="$OPTARG" ;;
    L ) S_EXPERIMENT_LABEL="$OPTARG" ;;
    S ) S_REFERENCE_STRAIN="$OPTARG" ;;
    d ) F_DEBUG="$OPTARG" ;;
    p ) F_RPROC="$OPTARG" ;;
    V ) F_VALIDATE_SG="$OPTARG" ;;
    P ) F_ONLY_PRIMARY="$OPTARG" ;;
    C ) F_DETECT_TRUNC="$OPTARG" ;;
    U ) F_COUNT_INT_COV="$OPTARG" ;;
    O ) F_HALF_OPEN="$OPTARG" ;;
    v ) F_VERBOSE="$OPTARG" ;;
    A ) F_CURATE_ALTPRIME="$OPTARG" ;;
    x ) F_SHARE_GENESTRUCT="$OPTARG" ;;
    i ) F_INSERT_IR="$OPTARG" ;;
    e ) F_INSERT_CE="$OPTARG" ;;
    E ) F_INSERT_IE="$OPTARG" ;;
    r ) F_REMOVE_SE="$OPTARG" ;;
    s ) F_INFER_SG="$OPTARG" ;;
    T ) F_RUN_AS="$OPTARG" ;;
    t ) S_AS_TYPES="$OPTARG" ;;
    n ) I_READ_LEN="$OPTARG" ;;
    F ) S_INFILE="$OPTARG" ;;
    X ) F_VAR_AWARE="$OPTARG" ;;
    h ) usage ;;
    \?) echo -e "UNKNOWN PARAMETER: $opt\n\n"; usage ;;
    esac
done

### check for mandatory parameters
[[ -z "$S_BAM_FNAME" ]] && echo -e "\nAlignment file name is mandatory!\n" && usage && exit 1
[[ -z "$S_OUT_DIRNAME" ]] && echo -e "\nOutput directory name is mandatory!\n" && usage && exit 1
[[ -z "$S_INFILE" ]] && [[ -z "$S_ANNO_FNAME" ]] && echo -e "\nAnnotation file name is mandatory!\n" && usage && exit 1

### prepare annotation if not in matlab format yet
if [ ! -z "$S_ANNO_FNAME" ]
then

    if [ "${S_ANNO_FNAME##*.}" != "mat" ]
    then
        S_ANNO_FNAME_N=${S_ANNO_FNAME%.*}.mat
        if [ -f "$S_ANNO_FNAME_N" ]
        then
            echo $S_ANNO_FNAME_N already exists
        else
            echo Converting annotation into matlab format: $S_ANNO_FNAME --> $S_ANNO_FNAME_N 
            ${SPLADDER_PYTHON_PATH} ${DIR}/../tools/ParseGFF.py ${S_ANNO_FNAME} ${S_ANNO_FNAME_N}
            ${DIR}/../bin/genes_cell2struct ${S_ANNO_FNAME_N}
        fi
        S_ANNO_FNAME=$S_ANNO_FNAME_N
    fi
fi

### assemble parameter string
PARAMS=""
for opt in S_BAM_FNAME S_OUT_DIRNAME S_LOG_FNAME S_ANNO_FNAME S_USER_FNAME I_CONFIDENCE I_INSERT_INTRON_ITER F_DEBUG F_VERBOSE F_INSERT_IR F_INSERT_CE F_INSERT_IE F_REMOVE_SE F_INFER_SG F_VALIDATE_SG S_MERGE_STRATEGY F_SHARE_GENESTRUCT S_REPLICATE_IDX S_EXPERIMENT_LABEL S_REFERENCE_STRAIN F_CURATE_ALTPRIME F_RPROC F_RUN_AS S_AS_TYPES I_READ_LEN S_INFILE F_HALF_OPEN F_ONLY_PRIMARY F_DETECT_TRUNC F_VAR_AWARE F_COUNT_INT_COV
do
    val=$(eval "echo \$${opt}")
    if [ ! -z "$val" ]
    then
        eval "PARAMS=\"$PARAMS${opt}:\${$opt};\""
    fi
done


### Index Bam files
echo "Indexing BAM files"
if [ "${S_BAM_FNAME##*.}" == "txt" ]
then
    cat ${S_BAM_FNAME} | while read CURR_BAMFILE
    do
        if [ ! -f ${CURR_BAMFILE}.bai ]
        then
            echo "Indexing $CURR_BAMFILE"
            ${SPLADDER_SAMTOOLS_BIN_DIR}/samtools index $CURR_BAMFILE
        else
            echo "$CURR_BAMFILE already indexed"
        fi
    done
else
    OLD_IFS=$IFS
    IFS=',' 
    for BAM_FILE in ${S_BAM_FNAME}
    do
        CURR_BAMFILE=$BAM_FILE
        if [ ! -f ${CURR_BAMFILE}.bai ]
        then
            echo "Indexing $CURR_BAMFILE"
            ${SPLADDER_SAMTOOLS_BIN_DIR}/samtools index $CURR_BAMFILE
        else
            echo "$CURR_BAMFILE already indexed"
        fi
    done
    IFS=$OLD_IFS
fi

### start the matlab/octave part of spladder
exec ${DIR}/start_interpreter.sh ${PROG%.sh} "$PARAMS"
