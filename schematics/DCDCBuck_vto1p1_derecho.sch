v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
N -110 60 -80 60 {lab=Vo}
N -30 60 10 60 {lab=#net1}
N 40 40 40 60 {lab=Vs}
N 40 40 70 40 {lab=Vs}
N 70 40 70 60 {lab=Vs}
N -60 40 -60 60 {lab=Vs}
N 0 40 40 40 {lab=Vs}
N 0 20 0 40 {lab=Vs}
N -60 40 0 40 {lab=Vs}
N -60 100 -60 120 {lab=Vg1}
N 40 100 40 120 {lab=Vg2}
N -110 30 -110 60 {lab=Vo}
C {sg13g2_pr/sg13_hv_nmos.sym} 40 80 3 0 {name=M2
l=0.45u
w=10u
ng=1
m=1
model=sg13_hv_nmos
spiceprefix=M
}
C {iopin.sym} 0 20 3 0 {name=p2 lab=Vs}
C {sg13g2_pr/sg13_hv_nmos.sym} -60 80 3 0 {name=M1
l=0.45u
w=10u
ng=1
m=1
model=sg13_hv_nmos
spiceprefix=M
}
C {iopin.sym} -60 120 3 1 {name=p4 lab=Vg1
}
C {iopin.sym} 40 120 3 1 {name=p5 lab=Vg2}
C {iopin.sym} -110 30 3 0 {name=p1 lab=Vo}
