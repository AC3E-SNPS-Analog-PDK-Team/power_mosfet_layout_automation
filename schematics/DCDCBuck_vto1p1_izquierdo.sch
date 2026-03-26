v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
N 20 90 90 90 {lab=Vs}
N 20 90 20 130 {lab=Vs}
N -30 90 20 90 {lab=Vs}
N 90 60 90 90 {lab=Vs}
N 70 60 90 60 {lab=Vs}
N -40 60 -30 60 {lab=Vs}
N -30 60 -30 90 {lab=Vs}
N -40 90 -30 90 {lab=Vs}
N 20 60 30 60 {lab=Vg2}
N -110 60 -80 60 {lab=Vg1}
N -110 50 -110 60 {lab=Vg1}
N 20 50 20 60 {lab=Vg2}
N 20 -30 20 -10 {lab=Vo}
N 20 -10 70 -10 {lab=Vo}
N -40 -10 20 -10 {lab=Vo}
N 70 -10 70 30 {lab=Vo}
N -40 -10 -40 30 {lab=Vo}
C {sg13g2_pr/sg13_hv_nmos.sym} 50 60 0 0 {name=M2
l=0.45u
w=10u
ng=1
m=1
model=sg13_hv_nmos
spiceprefix=M
}
C {iopin.sym} 20 130 0 0 {name=p2 lab=Vs}
C {sg13g2_pr/sg13_hv_nmos.sym} -60 60 0 0 {name=M1
l=0.45u
w=10u
ng=1
m=1
model=sg13_hv_nmos
spiceprefix=M
}
C {iopin.sym} -110 50 1 1 {name=p4 lab=Vg1
}
C {iopin.sym} 20 50 1 1 {name=p5 lab=Vg2}
C {iopin.sym} 20 -30 0 0 {name=p1 lab=Vo}
