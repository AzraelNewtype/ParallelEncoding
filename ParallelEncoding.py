#!/usr/bin/env python3
# -*- coding: utf-8-*-
""" Port of parallelencoding.cmd to python, cleaned from the ghastly batch
    script standards for PEP8 compliance (not yet). Also adds 10bit
    functionality.
"""

import optparse, os, re, shutil, subprocess, sys, tempfile, time

# user params
avs2yuv_path = 'C:/enc_tools/avs2yuv.exe'
x264_8_path = 'C:/enc_tools/x264.exe'
x264_10_path =  'C:/enc_tools/x264-10bit.exe'
ffms2_10bit_path = 'C:/avsfilters/ffms-10-bithack/ffms2.dll'
ffms2_8bit_path = 'C:/avsfilters/ffms2.dll'

x264_extra_params='--preset ultrafast --subme 1'

def final_script_suffix(avs):
    """ Use this function to add things to the final script that you always
        want but do not directly pertain to the split/join functionality.
    """
    avs.write('LoadPlugin("C:\\avsfilters\\dither-1.13.3\\dither.dll")\n')
    avs.write('Import("C:\\avsfilters\\dither-1.13.3\\dither.avsi")\n')
    avs.write('#dither_convey_yuv4xxp16_on_yvxx() # [HD]\n')
    avs.write('dither_resize16(848,480, kernel="spline64").ditherpost() # [SD][WR]\n')
    avs.write('scxvid("out.stats") # [WR]\n')
    avs.write('#TextSub("{0}") # [SD]\n'.format(script_out_path))

def generate_parallel_avs(avs_out, main_avs, avs_mem, total_threads, thread_num):
    """ generate_parallel_avs creates trimmed files for parallel encoding """
    parallel_avs = open(avs_out, 'w')
    parallel_avs.write('SetMemoryMax({0})\n'.format(avs_mem))
    parallel_avs.write('Import("{0}")\n'.format(main_avs))
    parallel_avs.write('start = (FrameCount() / {0}) * {1}\n'.format(total_threads, thread_num - 1))
    if(thread_num == total_threads):
        parallel_avs.write('end = FrameCount()\n')
    else:
        parallel_avs.write('end = start + (FrameCount() / {0}) + 100\n'.format(total_threads))
    parallel_avs.write('Trim(start,end)\n')

def generate_joined_avs(output_avs, lossless, avs_mem, total_threads, tenbit):
    """ generate_joined_avs joins lossless files from parallel encoding """
    joined_avs = open(final_avs, 'w')
    if tenbit:
        filter_path = os.path.normpath(ffms2_10bit_path)
    else:
        filter_path = os.path.normpath(ffms2_8bit_path)
    joined_avs.write('LoadPlugin("{0}")\n'.format(filter_path))
    joined_avs.write('#SetMemoryMax({0})\n'.format(avs_mem))
    for thread in range(1, total_threads + 1):
        write_source_line(joined_avs, lossless, thread, tenbit)
        if (thread == 1):
            joined_avs.write('total1 = tmp.Trim(0,tmp.FrameCount() - 51)\n')
        elif (thread == total_threads):
            #final thread
            joined_avs.write('total1 = total1 + tmp.Trim(51,tmp.FrameCount())\n')
        else:
            joined_avs.write('total1 = total1 + tmp.Trim(51,tmp.FrameCount() - 51)\n')
    joined_avs.write('total1\n')
    final_script_suffix(joined_avs)

def write_source_line(avs, lossless, num, tenbit):
    lossless_out = lossless.replace('[NUM]', str(num))
    if tenbit:
        colorspace = 'YV12_10-bit_hack'
    else:
        colorspace = 'YV12'
    avs.write('tmp = FFVideoSource("{0}",colorspace="{1}",track=-1,pp="")\n'.format(lossless_out,
                                                                                    colorspace))


#count_frames counts number of frames in AviSynth Script
def count_frames(script_in, proc):
    frame = [0, 0, 0, 0]
    a,tempYUV=tempfile.mkstemp()
    os.close(a)
    frames_cmd = '"{0}" -raw -frames 1 "[input]" -o "{1}"'.format(os.path.normpath(avs2yuv_path), tempYUV)
    if(options.usewine):
        frames_cmd = 'wine ' + frames_cmd.replace('[input]', 'Z:' + script_in.replace('/','\\'))
    else:
        frames_cmd = frames_cmd.replace('[input]', script_in)

    proc = subprocess.Popen(frames_cmd,shell=True,stdout=subprocess.PIPE,universal_newlines=True,stderr=subprocess.STDOUT)
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
    return (frame, proc)

parser = optparse.OptionParser(usage="usage: %prog [options] input.avs")
parser.add_option('-t', '--threads', type='int', dest='threads', default=4,
                  help="Number of parallel encodes to spawn")
parser.add_option('-m', '--max-memory', type='int', dest='AVS_Mem_Per_Thread', default=512,
                  help="Value for SetMemoryMax() in threads")
parser.add_option('-w', '--wine', action='store_true', dest='usewine', default=False,
                  help="Encoding on linux, so use wine")
parser.add_option('-n', '--no-avs2yuv', action='store_false', dest='useavs2yuv', default=True,
                  help="Do not use avs2yuv. Strange default action requires explicitly turning off.")
parser.add_option('-d', '--tenbit', action='store_true', dest='tenbit', default=False,
                  help="Turns on hi10p mode. [default=False]")
(options, args) = parser.parse_args()

if(options.usewine):
    options.useavs2yuv = True

if (options.threads < 2):
    print("I'm sorry, but there is currently no special case for a single thread.")
    raise SystemExit

total_threads = options.threads
avs_mem = options.AVS_Mem_Per_Thread

if len(args) < 1:
    print('No input file given. Use -h or --help for usage.')
    raise SystemExit

# Looping for multiple input is kinda stupid, loop elsewhere if you want multiple input
infile = args[0]
(fname, ext) = os.path.splitext(infile)
# ensure positional argument is a real avs file.
if(not os.path.exists(infile) or not os.path.isfile(infile) or ext.lower().find('.avs') == -1):
    print('Input file does not exist or is not an avisynth script.')
    raise SystemExit

# script vars
avs_in = os.path.abspath(infile)
proj_name = os.path.basename(fname)
script_out_path = os.path.dirname(os.path.abspath(infile)) + os.sep + proj_name + os.sep
split_script = script_out_path + proj_name + '.[NUM].avs'
final_avs = script_out_path + proj_name + '.joined.avs'
lossless_path = script_out_path + 'Lossless' + os.sep
split_output = lossless_path + proj_name + '.[NUM].mkv'
tenbit = options.tenbit

# remove old scripts and files before script is run
if os.path.isdir(script_out_path):
    shutil.rmtree(script_out_path)

# check to make sure dirs exist
for dir in (script_out_path, lossless_path):
    if not os.path.isdir(dir):
        os.makedirs(dir)

# create trimmed scripts
print('Creating trimmed scripts.')
if options.useavs2yuv:
    split_script_frames = list(range(total_threads))
    proc = list(range(total_threads))
for thread in range(1,total_threads + 1):
    new_split_script = split_script.replace('[NUM]', str(thread))
    if(options.usewine):
        generate_parallel_avs(new_split_script,'Z:' + avs_in.replace('/','\\'), avs_mem, total_threads, thread)
    else:
        generate_parallel_avs(new_split_script, avs_in, avs_mem, total_threads, thread)
    if(options.useavs2yuv):
        print('Counting frames in script {0}'.format(thread))
        (split_script_frames[thread-1],proc[thread-1]) = count_frames(new_split_script, proc[thread-1])

if(options.useavs2yuv):
    for thread in range(total_threads):
        proc[thread].wait()

if tenbit:
    x264_extra_params += ' --input-depth 16'
    x264_path = x264_10_path
else:
    x264_path = x264_8_path

# create cmd batch files
enc_cmd = ''
cmd_input = '"[input]"'
cmd_output = '"[output]"'
if(options.useavs2yuv):
    enc_cmd = enc_cmd + '"' + os.path.normpath(avs2yuv_path) + '" -raw ' + cmd_input + ' -o - | '
    if(int(split_script_frames[0][3]) > -1):
        if(tenbit):
            width = str(int(split_script_frames[0][0])//2)
        else:
            width = split_script_frames[0][0]
        cmd_input = "--input-res {0}x{1} ".format(width,split_script_frames[0][1])
        cmd_input += "--fps {0} --frames [frames] --demuxer raw -".format(split_script_frames[0][2])
enc_cmd = enc_cmd + '"' + os.path.normpath(x264_path) + '" ' + x264_extra_params + ' --crf 0 --threads 1 --thread-input --output ' + cmd_output + ' ' + cmd_input
proc = list(range(total_threads))
for thread in range(1, total_threads + 1):
    new_split_script = split_script.replace('[NUM]', str(thread))
    new_lossless = split_output.replace('[NUM]', str(thread))
    new_cmd = enc_cmd.replace('[input]', new_split_script)
    new_cmd = new_cmd.replace('[output]', new_lossless)
    if(options.useavs2yuv):
        new_cmd = new_cmd.replace('[frames]', split_script_frames[thread-1][3])
    if(options.usewine):
        new_cmd = 'wine ' + new_cmd
    print(new_cmd + '\n')
    proc[thread-1] = subprocess.Popen(new_cmd,shell=True)

for thread in range(total_threads):
    proc[thread].wait()

# create joined lossless script
print('Generating joined script.')


if(options.usewine):
    split_output = 'Z:' + split_output.replace('/','\\')

generate_joined_avs(final_avs, split_output, avs_mem, total_threads, tenbit)
