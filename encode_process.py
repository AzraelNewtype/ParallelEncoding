#!/usr/bin/env python3

import argparse
import glob
import os
import re
import shlex
import subprocess
import sys
import tempfile
import yaml

class Opts(object):
    pass

def load_settings(series):
    try:
        with open('encoder.yaml') as y:
            all_settings = yaml.load(y)
    except IOError:
        print("Cannot load encoder.yaml, cannot continue.")
        raise SystemExit

    settings = all_settings['Global']
    try:
        settings.update(all_settings['Series'][series])
    except KeyError:
        print('No entry for series "{0}" in encoder.yaml, the available options are:'.format(series))
        for series in all_settings['Series']:
            print(series)
        raise SystemExit

    return settings

def prepare_mode_avs(ep_num, mode):
    basename = "{0}.joined.avs".format(ep_num)
    with open(basename) as f:
        lines = f.readlines()

    outname = basename.replace("joined", mode)
    with open(outname, "w") as f:
        for raw_line in lines:
            line = raw_line.rstrip()
            if re.match("#", line):
                m = re.search("#(.+)#(.+)", line)
                if m and re.search("\[{0}\]".format(mode), m.group(2)):
                    line = m.group(1)
                else:
                    line = None
            if line:
                f.write("{0}{1}".format(line, os.linesep))

def get_audiofile_name(ep_num):
    basename = "{0}.avs".format(ep_num)
    with open(basename) as f:
        for line in f:
            m = re.search(r"source\(\"(.+)\"\)", line)
            if m:
                aacs = glob.glob("{0}*.aac".format(os.path.splitext(m.group(1))[0]))
                if len(aacs) > 0:
                    return aacs[0]

def get_stats_name(ep_num):
    basename = "{0}.WR.avs".format(ep_num)
    with open(basename) as f:
        for line in f:
            m = re.search(r"scxvid\(\"(.+)\"\)",line)
            if m:
                print(m.group(1))

def cut_audio_and_make_chapters(settings, ep_num, temp_name):
    aud_in = get_audiofile_name(ep_num)
    cmd = "{0}".format(settings["vfrpy"])
    cmd += ' -mr -i "{0}" -o {1}_aud.mka'.format(aud_in, ep_num)
    if temp_name:
        cmd += " -t {0}{1}.txt -c {2}.xml".format(settings['chapter_template_dir'], temp_name, ep_num)
    cmd +=" {0}.avs".format(ep_num)
    split_and_blind_call(cmd)

def encode_wr(settings, ep_num, prefix, temp_name):
    cut_audio_and_make_chapters(settings, ep_num, temp_name)
    prepare_mode_avs(ep_num, "WR")
    cmd = "{0} {3} --qpfile {1}.qpfile --acodec copy --audiofile {1}_aud.mka -o {2}{1}wr.mp4 {1}.WR.avs".format(settings["x264_8"], ep_num, prefix, settings["wr_opts"])
    split_and_blind_call(cmd)

def get_vid_info(settings, ep_num, mode):
    info = [0, 0, 0, 0]
    a, tempYUV = tempfile.mkstemp()
    os.close(a)
    avs_name = "{0}.{1}.avs".format(ep_num, mode)
    frames_cmd = '"{0}"'.format(os.path.normpath(settings["avs2yuv"]))
    frames_cmd += '-raw -frames 1 "{1}" -o "{0}"'.format(tempYUV, avs_name)

    proc = subprocess.Popen(frames_cmd,shell=True,stdout=subprocess.PIPE,universal_newlines=True,stderr=subprocess.STDOUT)
    proc.wait()
    p = re.compile ('.+: ([0-9]+)x([0-9]+), ([0-9]+/[0-9]+) fps, ([0-9]+) frames')
    result = False
    for line in proc.stdout:
        m = p.search(line)
        if m:
            info = [m.group(1), m.group(2), m.group(3), m.group(4)]
            result = True
            break
    if not result:
        print('Error: Could not count number of frames.')
        frame[3] = -1
    os.unlink(tempYUV)
    return(info)

def encode_sd(settings, ep_num, group):
    prepare_mode_avs(ep_num, "SD")
    out_name = "[{0}] {1} - {2}SD.mp4".format(group, settings["full_name"], ep_num)
    cmd = '"{2}" {3} --qpfile {0}.qpfile --acodec copy --audiofile {0}_aud.mka -o "{1}" {0}.SD.avs'.format(ep_num, out_name, settings["x264_8"], settings["sd_opts"])
    split_and_blind_call(cmd)

def encode_hd(settings, ep_num, tenbit, group):
    input_avs = "{0}.HD.avs".format(ep_num)
    if tenbit:
        frame_info = get_vid_info(settings, ep_num, "HD")
        tenbit_flags = "--input-depth 16 --input-res {0}x{1} --fps {2} --frames {3}".format(frame_info[0], frame_info[1], frame_info[2], frame_info[3])
        encoder_source = "{0} -raw {1} -o - | {2} {3}".format(settings["avs2yuv"], input_avs, settings["x264_10"], tenbit_flags)
    else:
        encoder_source = "{0} {1}".format(settings["x264_8"], input_avs)
    prepare_mode_avs(ep_num, "HD")
    cmd = "{0} {2} --qpfile {1}.qpfile -o {1}_vid.mkv {3}".format(settings["x264_8"], ep_num, settings["hd_opts"], input_avs)
    split_and_blind_call(cmd)
    muxed_name = mux_hd_raw(ep_num, group)

def mux_hd_raw(ep_num, group):
    out_name = "[{0}] {1} - {2}.mkv".format(group, settings["full_name"], ep_num)
    cmd = '"{0}" -o "{1}"  "--language" "1:jpn" "--default-track" "1:yes" "--forced-track" "1:no" "--display-dimensions" "1:1280x720" "-d" "1" "-A" "-S" "-T" "--no-global-tags" "--no-chapters" "{2}_vid.mkv" "--language" "1:jpn" "--default-track" "1:yes" "--forced-track" "1:no" "-a" "1" "-D" "-S" "-T" "--no-global-tags" "--no-chapters" "{2}_aud.mka" "--track-order" "0:1,1:1" "--chapters" "{2}.xml"'.format(settings["mkvmerge"], out_name, ep_num)
    cmd += mux_fonts_cmd(settings['fonts'])
    split_and_blind_call(cmd)
    return out_name

def mux_fonts_cmd(fonts):
    font_switches = ""
    for font in fonts:
        font_switches += ' --attachment-mime-type application/x-truetype-font'
        font_switches += ' --attachment-name "{0}"'.format(os.path.basename(font))
        font_switches += ' --attach-file "{0}"'.format(font)
    return font_switches

def split_and_blind_call(cmd):
    args = shlex.split(cmd)
    #subprocess.Popen(args)
    print(' '.join(args))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Commands to automate the crap out of encoding")
    parser.add_argument('series', help="Series name, corresponding to series top level in encoder.yaml")
    parser.add_argument('epnum', help="Episode number to process.", type=int)
    parser.add_argument('enc_type', choices=["sd", "hd", "wr"], help="Which set of encoder commands to run?")
    parser.add_argument('-t', '--template', dest='temp_name', help="Name of chapter template file with no .txt")
    parser.add_argument('-p', '--prefix', dest='prefix', help="Prefix to attach to output filename. Group tag goes here for HD/SD")
    parser.add_argument('-d', '--tenbit', dest='tenbit', action='store_true', default=False, help="Use 10bit encoder.")
    parser.add_argument('--version', action='version', version='0.1')
    args = parser.parse_args(namespace=Opts)
    settings = load_settings(Opts.series)
    if not Opts.prefix:
        prefix = ""
    else:
        prefix = Opts.prefix
    if Opts.enc_type == "wr":
        encode_wr(settings, Opts.epnum, prefix, Opts.temp_name)
    elif Opts.enc_type == "hd":
        encode_hd(settings, Opts.epnum, Opts.tenbit, prefix)
    elif Opts.enc_type == "sd":
        encode_sd(settings, Opts.epnum, prefix)
    else:
        print("You specified an invalid encode type. The options are 'wr', 'hd', or 'sd'.")
        raise SystemExit
