#!/usr/bin/env python3

import argparse
import glob
import os
import re
import shlex
import subprocess
import sys
import yaml

#This is ugly but I felt like not using a whole mess of different globals at least
# TODO: Split this hunk of shit into two config files: global and per-series
g_dic = {"mkvmerge" : "C:/Program Files (x86)/MKVtoolnix/mkvmerge.exe"}
g_dic["avs2yuv"] = "C:/enc_tools/avs2yuv.exe"
g_dic["vfrpy"] = "C:/enc_tools/vfr/vfr.py"
g_dic["chap_temp"] = "C:/enc_tools/"
g_dic["series"] = "Pirate Sentai Gokaiger"
g_dic["x264_8"] = "C:/enc_tools/x264.exe"
g_dic["x264_10"] = "C:/enc_tools/x264-10bit.exe"
g_dic["wr_dest"] = "C:/Dropbox/Over-Time/"
g_dic["hd_opts"] = "--preset veryslow --tune film --crf 23.5 --keyint 240 --colormatrix bt709 --level 4.1"
g_dic["wr_opts"] = "--profile main --preset ultrafast --tune film,fastdecode --level 3.1 --vbv-bufsize 14000 --vbv-maxrate 14000 --aq-mode 2 --keyint 240 --crf 38 --colormatrix bt709"
g_dic["sd_opts"] = "--profile main --level 3 --preset veryslow --crf 25 --keyint 240 --vbv-bufsize 8000 --vbv-maxrate 8000 --partitions p8x8,b8x8,i4x4 --tune film,fastdecode --colormatrix bt709 --sar 160:159"
g_fonts = ["C:/Users/Chris/Documents/Gokai/calibri.ttf",
           "C:/Users/Chris/Documents/Gokai/CAS_ANTI.TTF",
           "C:/Users/Chris/Documents/Gokai/CAS_ANTN.TTF"]


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

def cut_audio_and_make_chapters(ep_num, temp_name):
    aud_in = get_audiofile_name(ep_num)
    cmd = "{0}.avs {1} -mr -i '{2}' -o {0}_aud.mka".format(ep_num, g_dic["vfrpy"], aud_in)
    if temp_name:
        cmd += " -t {0}{1}.txt -c {2}.xml".format(g_dic['chap_temp'], temp_name, ep_num)
    split_and_blind_call(cmd)

def encode_wr(ep_num, prefix, temp_name):
    cut_audio_and_make_chapters(ep_num, temp_name)
    prepare_mode_avs(ep_num, "WR")
    cmd = "{0} {3} --qpfile {1}.qpfile --acodec copy --audiofile {1}_aud.mka -o {2}{1}wr.mp4 {1}.WR.avs".format(g_dic["x264_8"], ep_num,
                                                                                                                              prefix, g_dic["wr_opts"])
    split_and_blind_call(cmd)
    #move_wr_bits(ep_num, prefix)

def get_vid_info(ep_num, mode):
    info = [0, 0, 0, 0]
    a, tempYUV = tempfile.mkstemp()
    os.close(a)
    avs_name = "{0}.{1}.avs".format(ep_num, mode)
    frames_cmd = '"{0}" -raw -frames 1 "{2}" -o "{1}"'.format(os.path.normpath(avs2yuv_path), tempYUV, avs_name)

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

def encode_sd(ep_num, group):
    prepare_mode_avs(ep_num, "SD")
    out_name = "[{0}] {1} - {2}SD.mp4".format(group, g_dic["series"], ep_num)
    cmd = '"{2}" {3} --qpfile {0}.qpfile --acodec copy --audiofile {0}_aud.mka -o "{1}" {0}.SD.avs'.format(ep_num, out_name,
                                                                                                                         g_dic["x264_8"], g_dic["sd_opts"])
    split_and_blind_call(cmd)

def encode_hd(ep_num, tenbit, group):
    input_avs = "{0}.HD.avs".format(ep_num)
    if tenbit:
        frame_info = get_vid_info(ep_num, "HD")
        tenbit_flags = "--input-depth 16 --input-res {0}x{1} --fps {2} --frames {3}".format(frame_info[0], frame_info[1],
                                                                                            frame_info[2], frame_info[3])
        encoder_source = "{0} -raw {1} -o - | {2} {3}".format(g_dic["avs2yuv"], input_avs, g_dic["x264_10"], tenbit_flags)
    else:
        encoder_source = "{0} {1}".format(g_dic["x264_8"], input_avs)
    prepare_mode_avs(ep_num, "HD")
    cmd = "{0} {2} --qpfile {1}.qpfile -o {1}_vid.mkv {3}".format(g_dic["x264_8"], ep_num, g_dic["hd_opts"], input_avs)
    split_and_blind_call(cmd)
    muxed_name = mux_hd_raw(ep_num, group)

def mux_hd_raw(ep_num, group):
    out_name = "[{0}] {1} - {2}.mkv".format(group, g_dic["series"], ep_num)
    cmd = '"{0}" -o "{1}"  "--language" "1:jpn" "--default-track" "1:yes" "--forced-track" "1:no" "--display-dimensions" "1:1280x720" "-d" "1" "-A" "-S" "-T" "--no-global-tags" "--no-chapters" "{2}_vid.mkv" "--language" "1:jpn" "--default-track" "1:yes" "--forced-track" "1:no" "-a" "1" "-D" "-S" "-T" "--no-global-tags" "--no-chapters" "{2}_aud.mka" "--track-order" "0:1,1:1" "--chapters" "{2}.xml"'.format(g_dic["mkvmerge"], out_name, ep_num)
    cmd += mux_fonts_cmd()
    split_and_blind_call(cmd)
    return out_name

def mux_fonts_cmd():
    font_switches = ""
    for font in g_fonts:
        font_switches += ' --attachment-mime-type application/x-truetype-font'
        font_switches += ' --attachment-name "{0}"'.format(os.path.basename(font))
        font_switches += ' --attach-file "{0}"'.format(font)
    return font_switches

def split_and_blind_call(cmd):
    args = shlex.split(cmd)
    #subprocess.Popen(args)
    print(' '.join(args))

def move_wr_bits(ep_num, prefix):
    wr_cmd = "copy {0}{1}wr.mp4 {2}".format(prefix, ep_num, g_dic["wr_dest"])
    stats_in = get_stats_name(ep_num)
    stat_rename_cmd = "move {0} {1}{2}.stats".format(stats_in, prefix, ep_num)
    stat_out_cmd = "copy {0}{1}.stats {2}".format(prefix, ep_num, g_dic["wr_dest"])
    split_and_blind_call(wr_cmd)
    split_and_blind_call(stat_rename_cmd)
    split_and_blind_call(stat_out_cmd)

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
        encode_wr(Opts.epnum, prefix, Opts.temp_name)
    elif Opts.enc_type == "hd":
        encode_hd(Opts.epnum, Opts.tenbit, prefix)
