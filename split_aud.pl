#!/usr/bin/perl

use warnings;
use strict;
use Getopt::Std;
use POSIX qw(floor);

my %opts;
my $VERSION = "0.21";
getopts('vhmrf:o:l:i:', \%opts);

if ($opts{'h'}) {
	HELP_MESSAGE();
	exit 1;
}

my $infile = shift @ARGV;
if (!$infile) {
	print("Usage: split_aud.pl [options] infile.avs\n");
	exit 1;
}

# I must be permanently brain-damaged by avs or something
my $audfile	= $opts{'i'} ? $opts{'i'} : "${infile}.aac";
my $outfile	= $opts{'o'} ? $opts{'o'} : "${infile}.mka";
my $label	= $opts{'l'} ? $opts{'l'} : "trim";
my $fps		= $opts{'f'} ? $opts{'f'} : 30000/1001;
my $merge	= $opts{'m'} ? $opts{'m'} : 0;
my $remove	= $opts{'r'} ? $opts{'r'} : 0;
my $verbose	= $opts{'v'} ? $opts{'v'} : 0;
my $offset	= 0;
my $includefirst	= 0;
my ($fps_num, $fps_den);
my @cuttimes;

die("I don't see any $audfile here") unless -e $audfile;

$offset = $1 if ($audfile =~ /DELAY ([-]?\d+)/);
if ($fps =~ m!(\d+)(?:/|:)(\d+)!) {
	$fps = 0;
	($fps_num, $fps_den) = ($1, $2);
}


open(INFILE, "<", $infile) or die ("Couldn't open ${infile}: $!");

while (<INFILE>) {
	next unless (/$label/i and /trim/i);
	# end frame is inclusive but the timestamp generated is for the start of the frame, hence add 1
	push(@cuttimes, frame2time($1), frame2time($2+1)) while (/trim\((\d+),(\d+)\)/ig);
	if ($cuttimes[0] eq "00:00:00.000") {
		$includefirst = 1;
		shift @cuttimes; #don't try to split at 00:00:00.000, it gives nonsense results
	}
	last if @cuttimes; # don't bother looking any further
}

die("No trims found on any line(s) marked by \"${label}\" in $infile") unless @cuttimes;

if ($verbose) {
	print "Executing: ", join(" ", "mkvmerge", "-o", "${outfile}.split.mka",
		"--sync", "0:$offset", "$audfile", "--split", "timecodes:" . join(',',@cuttimes), "\n\n");
}

system("mkvmerge", "-o", "${outfile}.split.mka", "--sync", "0:$offset", "$audfile",
	"--split", "timecodes:" . join(',',@cuttimes));
die("Failed to execute mkvmerge: $!") if ($? == -1);

exit 0 unless $merge;


# attempt to merge the files
my $num_files = (scalar @cuttimes) + 1;
my @mergefiles;

foreach (1 .. $num_files) {
	if (($includefirst and ($_ % 2) != 0) or (not $includefirst and ($_ % 2) == 0)) {
		push(@mergefiles, sprintf("+${outfile}.split-%03d.mka",$_));
	}	
}

$mergefiles[0] = substr($mergefiles[0], 1); # chop off the + from the first filename

if ($verbose) {
	print("\n\nMerging: ", join(" ",@mergefiles), "\n\n");
}

system("mkvmerge", "-o", $outfile, @mergefiles);
die("Failed to execute mkvmerge: $!") if ($? == -1);

if ($remove) {
	foreach (1 .. $num_files) {
		my $fn = sprintf("${outfile}.split-%03d.mka",$_);
		print "\n\nDeleting: $fn \n";
		unlink $fn;
	}
}

exit 0;


###################

sub frame2time {
	my $fn = shift;
	my $ts;
	if ($fps) {
		$ts = round($fn*(1000/$fps));
	} else {
		$ts = round((1000 * $fn * $fps_den) / $fps_num);
	}
	my ($h, $m, $s, $ms) = (0,0,0,0);
	while ($ts >= 3_600_000) {
		$ts -= 3_600_000; $h++;
	}
	while ($ts >= 60_000) {
		$ts -= 60_000; $m++;
	}
	while ($ts >= 1_000) {
		$ts -= 1_000; $s++;
	}
	$ms = $ts;
	
	return sprintf("%02d:%02d:%02d.%03d", $h, $m, $s, $ms);
}

sub round {
	my $n = shift;
	return floor($n+0.5);
}

sub HELP_MESSAGE {
	print <<EOF;
$0 $VERSION
Usage: split_aud.pl [options] SPLITFILE
Where SPLITFILE is the Avisynth script in which to look for trim() statements.

Options:
-i INFILE
    The filename passed to mkvmerge as the input file. Default: SPLITFILE.aac

-o OUTFILE
    The filename passed to mkvmerge as the output file. Default: INFILE.mka

-l LABEL
    Look for a trim() statement only on lines matching LABEL, interpreted as
    a regular expression. Default: trim (that means, use the first trim
    line found).

-f FRAMERATE
    The framerate at which the trim() frame numbers are converted to timestamps.
    Default: 30000/1001 (NTSC).
    Note: both floats and rational numbers (using / or : as a separator)
    are accepted.

-m
    Attempt to merge the files back together after splitting. Default: no.

-v
    Be verbose. Default: no.
    
-r
    Remove splitted files after merging. Has no effect unless -m is also
    specified. Default: no.
EOF
}

