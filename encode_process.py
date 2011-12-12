#!/usr/bin/env python

import shlex, subprocess, re, sys, os, glob

#This is ugly but I felt like not using a whole mess of different globals at least
g_dic = {}
g_dic["vfrpy"] = "C:/enc_tools/vfr/vfr.py"
g_dic["chap_temp"] = "C:/enc_tools/"
g_dic["x264_8"] = "C:/enc_tools/x264.exe"
g_dic["wr_dest"] = "C:/Users/Chris/Dropbox/Over-Time/"

def prepare_mode_avs(ep_num, mode):
    basename = "{0}.joined.avs".format(ep_num)
    with open(basename) as f:
        lines = f.readlines()

    outname = basename.replace("joined", mode)
    with open(outname, "w") as f:
        for raw_line in lines:
            line = raw_line.rstrip()
            if re.match("##", line):
                m = re.search(r"##(.+)#(.+)", line)
                if re.search("\[{0}\]".format(mode), m.group(2)):
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
    cmd = "{1} -mr -i '{4}' -o {0}_aud.mka -t {2}{3}.txt -c {0}.xml {0}.avs".format(
        ep_num, g_dic["vfrpy"], g_dic["chap_temp"], temp_name, aud_in)
    args = shlex.split(cmd)
    p = subprocess.Popen(args)

def encode_wr(ep_num, prefix, temp_name):
    #cut_audio_and_make_chapters(ep_num, temp_name)
    prepare_mode_avs(ep_num, "WR")
    cmd = "{0} --profile main --preset ultrafast --tune film,fastdecode --level 3.1 --vbv-bufsize 14000 --vbv-maxrate 14000 --aq-mode 2 --keyint 240 --crf 38 --colormatrix bt709 --qpfile {1}.qpfile --acodec copy --audiofile {1}_aud.mka --sar 160:159 -o {2}{1}wr.mp4 {1}.WR.avs".format(g_dic["x264_8"], ep_num, prefix)
    split_and_blind_call(cmd)
    move_wr_bits(ep_num, prefix)

def split_and_blind_call(cmd):
    args = shlex.split(cmd)
    subprocess.Popen(args)

def move_wr_bits(ep_num, prefix):
    wr_cmd = "copy {0}{1}wr.mp4 {2}".format(prefix, ep_num, g_dic["wr_dest"])
    stats_in = get_stats_name(ep_num)
    stat_rename_cmd = "move {0} {1}{2}.stats".format(stats_in, prefix, ep_num)
    stat_out_cmd = "copy {0}{1}.stats {2}".format(prefix, ep_num, g_dic["wr_dest"])
    split_and_blind_call(wr_cmd)
    split_and_blind_call(stat_rename_cmd)
    split_and_blind_call(stat_out_cmd)

if __name__ == "__main__":
    print("What")
