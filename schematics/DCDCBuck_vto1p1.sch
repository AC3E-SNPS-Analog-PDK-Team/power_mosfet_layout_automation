v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
N 0 70 0 80 {
lab=Vs}
N -70 40 -40 40 {
lab=Vi}
N 0 0 0 10 {
lab=Vo}
N 0 0 40 0 {
lab=Vo}
N 0 40 20 40 {
lab=Vs}
N 20 40 20 80 {
lab=Vs}
N 0 80 20 80 {
lab=Vs}
C {sg13g2_pr/sg13_hv_nmos.sym} -20 40 0 0 {name=M2
l=0.45u
w=10u
ng=1
m=200
model=sg13_hv_nmos
spiceprefix=M
}
C {iopin.sym} 40 0 0 0 {name=p3 lab=Vo}
C {iopin.sym} -70 40 0 1 {name=p1 lab=Vi}
C {iopin.sym} 0 80 1 0 {name=p2 lab=Vs}
