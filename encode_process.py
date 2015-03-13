#!/usr/bin/env python3

import argparse
import glob
import os
import re
import shlex
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:
    print("You need to install PyYaml for this to work.")
    raise SystemExit

class Opts(object):
    pass

def load_settings(series):
    try:
        script_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
        yaml_loc = os.path.join(script_dir,"encoder.yaml")
        with open(yaml_loc) as y:
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

def prepare_mode_avs(ep_num, mode, script):
    basename = "{0}/{0}.joined.avs".format(ep_num)
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
                if not script == "" and re.search(r'\[\[script\]\]', line):
                    script_loc = os.path.abspath(script)
                    print(line)
                    print(script_loc)
                    line = 'TextSub("{0}")'.format(script_loc)
                f.write("{0}{1}".format(line, os.linesep))

def get_audiofile_name(ep_num):
    basename = "{0}.avs".format(ep_num)
    with open(basename) as f:
        for line in f:
            m = re.search(r"source\(\"(.+)?\"(,.+)*?\)", line)
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

def cut_audio(settings, ep_num):
    aud_in = get_audiofile_name(ep_num)
    if settings["vfrpy"]:
        cmd = settings["vfrpy"]
    elif settings["splitaud"]:
        cmd = settings["splitaud"]
    else:
        print("You don't have an audio cutter path defined in encoder.yaml, give the path to vfr.py or split_aud.pl")
        raise SystemExit
    cmd += ' -mr -i "{0}" -o {1}_aud.mka'.format(aud_in, ep_num)
    cmd +=" {0}.avs".format(ep_num)
    split_and_blind_call(cmd, True)


def make_chapters(settings, ep_num, temp_name, mp4):
    cmd = "{0}".format(settings["vfrpy"])
    if mp4:
        cmd += " -n {0}{1}-names.txt -c {2}ch.txt".format(settings['chapter_template_dir'], temp_name, ep_num)
    else:
        cmd += " -t {0}{1}.txt -c {2}.xml".format(settings['chapter_template_dir'], temp_name, ep_num)
    cmd +=" {0}.avs".format(ep_num)
    split_and_blind_call(cmd, True)

def encode_wr(settings, ep_num, prefix, temp_name):
    cut_audio(settings, ep_num)
    print(temp_name)
    if temp_name:
        make_chapters(settings, ep_num, temp_name, False)
        if settings["mp4chapters"]:
            make_chapters(settings, ep_num, temp_name, True)
    prepare_mode_avs(ep_num, "WR", "")
    try:
        tc_str = "--tcfile-in {0}".format(settings["tc"])
    except KeyError:
        tc_str = ""
    cmd = ("{0} {3} --qpfile {1}.qpfile --acodec copy --audiofile "
          "{1}_aud.mka -o {2}{1}wr.mkv {1}/{1}.WR.avs {4} --chapter "
          "{1}.xml".
          format(settings["x264_8"], ep_num, prefix, settings["wr_opts"], 
                 tc_str))
    split_and_blind_call(cmd)

def get_vid_info(settings, ep_num, mode):
    info = [0, 0, 0, 0]
    a, tempYUV = tempfile.mkstemp()
    os.close(a)
    avs_name = "{0}/{0}.{1}.avs".format(ep_num, mode)
    frames_cmd = '"{0}"'.format(os.path.normpath(settings["avs2yuv"]))
    frames_cmd += ' -raw -frames 1 "{1}" -o "{0}"'.format(tempYUV, avs_name)

    print(frames_cmd)
    proc = subprocess.Popen(frames_cmd,shell=True,stdout=subprocess.PIPE,universal_newlines=True,stderr=subprocess.STDOUT)
    proc.wait()
    p = re.compile ('.+: ([0-9]+)x([0-9]+), ([0-9]+/[0-9]+) fps, ([0-9]+) frames')
    for line in proc.stdout:
        m = p.search(line)
        if m:
            os.unlink(tempYUV)
            return [m.group(1), m.group(2), m.group(3), m.group(4)]
    os.unlink(tempYUV)
    print('Error: Could not count number of frames.')
    raise SystemExit

def encode_sd(settings, ep_num, group):
    prepare_mode_avs(ep_num, "SD", settings["script"])
    if settings["ver"]:
        name_ep_num = "{0}v{1}".format(ep_num, settings["ver"])
    else:
        name_ep_num = ep_num
    out_name = "out/[{0}] {1} - {2}SD.mp4".format(group, settings["full_name"], name_ep_num)
    if os.path.exists("{0}ch.txt".format(ep_num)):
        chaps = "--chapter {0}ch.txt".format(ep_num)
    else:
        chaps = ""
    try:
        tc_str = " --tcfile-in {0}".format(settings["tc"])
    except KeyError:
        tc_str = ""
    cmd = '"{2}" {3} --qpfile {0}.qpfile --acodec copy --audiofile {0}_aud.mka -o "{1}" {4}{5} {0}/{0}.SD.avs'.format(
        ep_num, out_name, settings["x264_8"], settings["sd_opts"], chaps, tc_str)
    split_and_blind_call(cmd)

def encode_hd(settings, ep_num, tenbit, group):
    prepare_mode_avs(ep_num, "HD", "")
    input_avs = "{0}/{0}.HD.avs".format(ep_num)
    hd_opts = settings["hd_opts"].rstrip()
    if tenbit:
        frame_info = get_vid_info(settings, ep_num, "HD")
        width = int(frame_info[0])//2 
        fps = eval(frame_info[2])
        try:
            fps_str = "--tcfile-in {0}".format(settings["tc"])
        except KeyError:
            fps_str = "--fps {0}".format(fps)
        res = "{0}x{1}".format(width, frame_info[1])
        tenbit_flags = ("--demuxer raw --input-depth {3} --input-res {0} {1} --frames {2} - ".
            format(res, fps_str, frame_info[3], settings["avs_depth"]))
        encoder_source = ("{0} -raw {1} -o - | {2} {3}".
            format(settings["avs2yuv"], input_avs, settings["x264_10"], tenbit_flags))
    else:
        encoder_source = "{0} {1}".format(settings["x264_8"], input_avs)
    cmd = "{0} {2} --qpfile {1}.qpfile -o {1}_vid.mkv".format(encoder_source, ep_num, hd_opts)
    bat = open('hd.bat', 'w')
    bat.write(cmd.replace('/','\\'))
    bat.write("{0}{0}".format(os.linesep))
    bat.close()
    split_and_blind_call('hd.bat')
    os.unlink('hd.bat')
    return mux_hd_raw(ep_num, group, res)

def mux_hd_raw(ep_num, group, res):
    out_name = "[{0}] {1} - {2}.mkv".format(group, settings["full_name"], ep_num)
# the first track has been 0 for a while now, so let's use that instead of requiring old versions
    cmd = '"{0}" -o "out/{1}"  "--language" "0:jpn" "--default-track" "0:yes" "--forced-track" "0:no"'.format(settings["mkvmerge"], out_name)
# Add in tags
    if os.path.exists("{0}tags.xml".format(ep_num)):
        cmd += ' "--tags" "0:{0}tags.xml"'.format(ep_num)
    cmd += ' "--display-dimensions" "0:{1}" "-d" "0" "-A" "-S" "-T" "--no-global-tags" "--no-chapters" "{0}_vid.mkv" "--language" "0:jpn" "--default-track" "0:yes" "--forced-track" "0:no" "-a" "0" "-D" "-S" "-T" "--no-global-tags" "--no-chapters" "{0}_aud.mka" "--track-order" "0:0,1:0" "--chapters" "{0}.xml"'.format(ep_num, res)
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


def split_and_blind_call(cmd, is_python=False):
    args = shlex.split(cmd)
    print(' '.join(args))
    if is_python:
        args.insert(0, sys.executable)
    f = subprocess.Popen(args)
    f.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Commands to automate the crap out of encoding")
    parser.add_argument('series', help="Series name, corresponding to series top level in encoder.yaml")
    parser.add_argument('epnum', help="Episode number to process.", type=int)
    parser.add_argument('enc_type', choices=["sd", "hd", "wr"], help="Which set of encoder commands to run?")
    parser.add_argument('-t', '--template', dest='temp_name', help="Name of chapter template file with no .txt")
    parser.add_argument('-p', '--prefix', dest='prefix', help="Prefix to attach to output filename. Group tag goes here for HD/SD")
    parser.add_argument('-d', '--tenbit', dest='tenbit', action='store_true', default=False, help="Use 10bit encoder.")
    parser.add_argument('--version', action='version', version='0.1')
    parser.add_argument('-s', '--script', dest="script", help="Filename of ass script. Replaces [[script]] in out template.")
    parser.add_argument('-V', '--release-version', dest="ver", help="Release version numberfor use with updated encodes, primarily SD probably.")
    parser.add_argument('-c', '--tcfile', dest="tc", help="External timecodes file for HD/SD encodes.")
    args = parser.parse_args(namespace=Opts)
    settings = load_settings(Opts.series)

    settings["ver"] = Opts.ver

    if Opts.tc:
        settings["tc"] = Opts.tc
    if not Opts.prefix:
        prefix = ""
    else:
        prefix = Opts.prefix
    if not Opts.temp_name:
        temp_name = None
    else:
        temp_name = Opts.temp_name
    if Opts.epnum < 10:
        epnum = "0" + str(Opts.epnum)
    else:
        epnum = str(Opts.epnum)
    if not Opts.script:
        settings["script"] = ""
    else:
        settings["script"] = Opts.script
    if Opts.enc_type == "wr":
        if settings["default_template"] and not temp_name:
            temp_name = settings["default_template"]
        if not Opts.prefix and settings["wr_prefix"]:
            prefix = settings["wr_prefix"]
        encode_wr(settings, epnum, prefix, temp_name)
    elif Opts.enc_type == "hd":
        if settings["hd_hi10p"] or Opts.tenbit:
            tenbit = True
        else:
            tenbit = False
        if not Opts.prefix and settings["hd_prefix"]:
            prefix = settings["hd_prefix"]
        encode_hd(settings, epnum, tenbit, prefix)
    elif Opts.enc_type == "sd":
        if not Opts.prefix and settings["sd_prefix"]:
            prefix = settings["sd_prefix"]
        encode_sd(settings, epnum, prefix)
    else:
        print("You specified an invalid encode type. The options are 'wr', 'hd', or 'sd'.")
        raise SystemExit
