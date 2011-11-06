#!/usr/bin/env python3
# -*- coding: utf-8-*-
""" Port of parallelencoding.cmd to python, cleaned from the ghastly batch
    script standards for PEP8 compliance (not yet). Also adds 10bit
    functionality.
"""

import optparse, os, re, shutil, subprocess, sys, tempfile, time

# user params
avs2yuv_path='C:/encoding/avs2yuv.exe'
x264_path='C:/encoding/x264/x264-10bit.exe'
ffms2_10bit_path='C:/encoding/oldplugins/ffms2-10bit.dll'

x264_extra_params='--preset ultrafast --subme 1 --input-depth 16'

# generate_parallel_avs creates trimmed files for parallel encoding
def generate_parallel_avs(avs_out, main_avs, avs_mem, total_threads, thread_number):
    parallel_avs = open(avs_out, 'w')
    parallel_avs.write('SetMemoryMax({0})\n'.format(avs_mem))
    parallel_avs.write('Import("{0}")\n'.format(main_avs))
    parallel_avs.write('start = (FrameCount() / {0}) * {1}\n'.format(total_threads, thread_num - 1))
    if(thread_num == total_threads):
        parallel_avs.write('end = FrameCount()\n')
    else:
        parallel_avs.write('end = start + (FrameCount() / {0}) + 100\n'.format(total_threads))
    parallel_avs.write('Trim(start,end)\n')

#generate_joined_avs joins lossless files from parallel encoding
def generate_joined_avs(output_avs, lossless, avs_mem, total_threads):
    joined_avs = open(_OutputAviSynthScript, 'w')
    joined_avs.write('LoadPlugin("{0}")\n'.format(os.path.normpath(ffms2_10bit_path)))
    joined_avs.write('#SetMemoryMax({0})\n'.format(avs_mem)
    for thread in range(1, total_threads + 1):
        write_source_line(joined_avs, lossless, thread)
        if (thread == 1):
            joined_avs.write('total1 = tmp.Trim(0,tmp.FrameCount() - 51)\n')
        elif (thread == total_threads - 1):
            #final thread
            joined_avs.write('total1 = total1 + tmp.Trim(51,tmp.FrameCount())\n')
        else:
            joined_avs.write('total1 = total1 + tmp.Trim(51,tmp.FrameCount() - 51)\n')
    joined_avs.write('total1\n')

def write_source_line(avs, lossless, num):
    lossless_out = lossless.replace('[NUM]', str(num))
    avs.write('tmp = FFVideoSource("{0}",colorspace="YV12_10-bit_hack",track=-1,pp="")\n'.format(lossless_out))


#count_frames counts number of frames in AviSynth Script
def count_frames(AviSynthScript, proc):
    frame = [0, 0, 0, 0]
    a,tempYUV=tempfile.mkstemp()
    os.close(a)
    frames_cmd = '"{0}" -raw -frames 1 "[input]" -o "{1}"'.format(os.path.normpath(avs2yuv_path), tempYUV)
    if(options.usewine):
        frames_cmd = 'wine ' + frames_cmd.replace('[input]', 'Z:' + AviSynthScript.replace('/','\\'))
        proc = subprocess.Popen(frames_cmd,shell=True,stdout=subprocess.PIPE,universal_newlines=True,stderr=subprocess.STDOUT)
    else:
        frames_cmd = '"' + frames_cmd.replace('[input]', AviSynthScript) + '"'
        proc = subprocess.Popen('"' + frames_cmd + '"',shell=True,stdout=subprocess.PIPE,universal_newlines=True,stderr=subprocess.STDOUT)
    proc.wait()
    p = re.compile ('.+: ([0-9]+)x([0-9]+), ([0-9]+/[0-9]+) fps, ([0-9]+) frames')
    result = False
    for line in proc.stdout:
        m = p.search(line)
        if m:
            frame = [m.group(1), m.group(2), m.group(3), m.group(4)]
            result = True
            break
    if not result:
        print('Error: Could not count number of frames.')
        frame[3] = -1
    os.unlink(tempYUV)
    return (frame,proc)

parser = optparse.OptionParser()
parser.add_option('-t', '--threads', type='int', dest='threads', default=4, help="Number of parallel encodes to spawn")
parser.add_option('-m', '--max-memory', type='int', dest='AVS_Mem_Per_Thread', default=512, help="Value for SetMemoryMax() in threads")
parser.add_option('-w', '--wine', action='store_true', dest='usewine', default=False, help="Encoding on linux, so use wine")
parser.add_option('-a', '--avs2yuv', action='store_true', dest='useavs2yuv', default=True, help="Use avs2yuv piping [default]")
(options, args) = parser.parse_args()

if(options.usewine):
    options.useavs2yuv = True

if (options.threads < 2):
    print("I'm sorry, but there is currently no special case for a single thread.")
    raise SystemExit

total_threads = options.threads
_AviSynthMemoryPerThread = options.AVS_Mem_Per_Thread

for file in args:
    (_path, _ext) = os.path.splitext(file)
    # initial test
    if(os.path.exists(file)==False or os.path.isfile(file)==False or _ext.lower().find('.avs')==-1):
        print('No input AviSynth Script specified.')
        print('Script quitting.')

    # script vars
    _InputAviSynthScript = os.path.abspath(file)
    _ProjectName = os.path.basename(_path)
    _ScriptsOutputPath = os.path.dirname(os.path.abspath(file)) + os.sep + _ProjectName + os.sep
    _ThreadScript = _ScriptsOutputPath + _ProjectName + '.[NUM].avs'
    _OutputAviSynthScript = _ScriptsOutputPath + _ProjectName + '.joined.avs'
    _LosslessOutputPathPE = _ScriptsOutputPath + 'Lossless' + os.sep
    _ThreadedLosslessFile = _LosslessOutputPathPE + _ProjectName + '.[NUM].mkv'

    # remove old scripts and files before script is run
    if(os.path.isdir(_ScriptsOutputPath)==True):
        shutil.rmtree(_ScriptsOutputPath)

    # check to make sure dirs exist
    for dir in (_ScriptsOutputPath, _LosslessOutputPathPE):
        if(os.path.isdir(dir)==False):
            os.makedirs(dir)

    # create trimmed scripts
    print('Creating trimmed scripts.')
    if(options.useavs2yuv):
        _ThreadScriptFrame = list(range(total_threads))
        proc = list(range(total_threads))
    for thread in range(1,total_threads + 1):
        _NewThreadScript = _ThreadScript.replace('[NUM]', str(thread))
        if(options.usewine):
            generate_parallel_avs(_NewThreadScript,'Z:' + _InputAviSynthScript.replace('/','\\'),_AviSynthMemoryPerThread,total_threads,_CurrentThread)
        else:
            generate_parallel_avs(_NewThreadScript,_InputAviSynthScript,_AviSynthMemoryPerThread,total_threads,_CurrentThread)
        if(options.useavs2yuv):
            print('Counting frames in script {0}'.format(thread))
            (_ThreadScriptFrame[thread-1],proc[thread-1]) = count_frames(_NewThreadScript, proc[thread-1])

    if(options.useavs2yuv):
        for thread in range(total_threads):
            proc[thread].wait()

    # create cmd batch files
    _CmdLinePE = ''
    _CmdLineInput = '"[input]"'
    _CmdLineOutput = '"[output]"'
    if(options.useavs2yuv):
        _CmdLinePE = _CmdLinePE + '"' + os.path.normpath(avs2yuv_path) + '" -raw ' + _CmdLineInput + ' -o - | '
        _CmdLineInput = '--frames [frames] --demuxer raw -'
        if(_ThreadScriptFrame[0][3] > -1):
            _CmdLineInput = '--input-res ' + repr(int(_ThreadScriptFrame[0][0])/2) + 'x' + _ThreadScriptFrame[0][1] + ' --fps ' + _ThreadScriptFrame[0][2] + ' ' + _CmdLineInput
    _CmdLinePE = _CmdLinePE + '"' + os.path.normpath(x264_path) + '" ' + x264_extra_params + ' --crf 0 --threads 1 --thread-input --output ' + _CmdLineOutput + ' ' + _CmdLineInput
    proc = list(range(total_threads))
    for thread in range(total_threads):
        _CurrentThread = thread+1
        _NewThreadScript = _ThreadScript.replace('[NUM]', repr(_CurrentThread))
        _NewLosslessFile = _ThreadedLosslessFile.replace('[NUM]', repr(_CurrentThread))
        _NewCmdLinePE = _CmdLinePE.replace('[input]', _NewThreadScript)
        _NewCmdLinePE = _NewCmdLinePE.replace('[output]', _NewLosslessFile)
        if(options.useavs2yuv):
            _NewCmdLinePE = _NewCmdLinePE.replace('[frames]', _ThreadScriptFrame[thread][3])
        if(options.usewine):
            _NewCmdLinePE = 'wine ' + _NewCmdLinePE
            print(_NewCmdLinePE + '\n')
            proc[thread] = subprocess.Popen(_NewCmdLinePE,shell=True)
        else:
            _NewCmdLinePE = '"' + _NewCmdLinePE + '"'
            print(_NewCmdLinePE + '\n')
            proc[thread] = subprocess.Popen('"' + _NewCmdLinePE + '"',shell=True)

    for thread in range(total_threads):
        proc[thread].wait()

    # create joined lossless script
    print('Generating joined script.')
    if(options.usewine):
        generate_joined_avs(_OutputAviSynthScript,'Z:' + _ThreadedLosslessFile.replace('/','\\'),_AviSynthMemoryPerThread,total_threads)
    else:
        generate_joined_avs(_OutputAviSynthScript,_ThreadedLosslessFile,_AviSynthMemoryPerThread,total_threads)
