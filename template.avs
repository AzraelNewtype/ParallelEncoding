LoadPlugin("C:\avsfilters\tdeint.dll")
LoadPlugin("C:\avsfilters\tmm.dll")
LoadPlugin("C:\avsfilters\nnedi3.dll")
LoadPlugin("C:\avsfilters\mt_masktools-26.dll")
LoadPlugin("C:\avsfilters\dither-1.13.1\dither.dll")
LoadPlugin("C:\avsfilters\dither-1.13.1\dfttest.dll")
Import("C:\avsfilters\dither-1.13.1\dither.avsi")
Import("C:\avsfilters\dither-1.13.1\mt_xxpand_multi.avsi")

SetMemoryMax(750)

dgdecode_Mpeg2source("[[d2v]]")

spline64resize(1280,height(),4,0,-6,0)
/*
dt = TDeint(order=1,field=1,type=1,edeint=nnedi3(field=1,threads=2),emask=TMM(order=1,field=1))
tfm(pp=5,mode=2,order=1,slow=1,y0=58,y1=140,clip2=dt)

#Cold Op               OP             Part A            Part B             ED                 Preview     
[[trims:6]]

noMolest=last
crop(0,0,0,-152)

tdecimate(clip2=noMolest)

spline64resize(1280,720,0,2,0,-2)

dfttest(sigma=8,tbsize=3,sbsize=18,sosize=9,lsb=true).ditherpost()
*/
