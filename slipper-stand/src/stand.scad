// 単位 mm。前後各2足、2段。正面=+Y。
part = "assembly";
$fn = 24;
pitch = 310;
clearance = 0.6; // 角軸8 mmに対する穴の全幅方向余裕。

// 面は平面を残し、全ての外縁を球面でつなぐ。
module round_box(size, r=2) {
    hull() for(x=[r,size[0]-r]) for(y=[r,size[1]-r]) for(z=[r,size[2]-r])
        translate([x,y,z]) sphere(r=r,$fn=16);
}
module round_profile(r=0.5) {
    offset(r=r) offset(delta=-r) children();
}
module soft_extrude(h,r=0.5) {
    minkowski() {
        translate([0,0,r]) linear_extrude(height=h-2*r)
            offset(delta=-r) children();
        sphere(r=r,$fn=12);
    }
}
module pin_hole(x,y,z,length=50,gap=clearance) {
    module aperture() {
        offset(r=0.9) square([8+gap-1.8,8+gap-1.8],center=true);
    }
    translate([x,y-0.05,z]) rotate([-90,0,0]) linear_extrude(height=length+0.1)
        aperture();
    // 穴口は0.3 mm面取りし、指に触れる切り口を残さない。
    wide=(8+gap+0.6)/(8+gap);
    translate([x,y-0.01,z]) rotate([-90,0,0]) linear_extrude(height=0.31,scale=1/wide)
        scale([wide,wide]) aperture();
    translate([x,y+length-0.3,z]) rotate([-90,0,0]) linear_extrude(height=0.31,scale=wide)
        aperture();
}
module base() {
    difference() {
        union() {
            translate([-140,-185,0]) round_box([280,250,16],5);
            translate([-35,-80,10]) round_box([70,40,76],3);
        }
        translate([-25-clearance/2,-70-clearance/2,16])
            linear_extrude(height=80) offset(r=2)
                translate([2,2]) square([50+clearance-4,20+clearance-4]);
        for(z=[36,56]) pin_hole(0,-80,z,40);
        for(x=[-120,40]) translate([x,-140,8]) round_box([80,160,20],3);
    }
}
module mast() {
    difference() {
        translate([-25,-70,0]) round_box([50,20,pitch],2);
        for(z=[20,40,182,196,270,290]) pin_hole(0,-70,z,20);
    }
}
module splice() {
    difference() {
        translate([-25,-78,0]) round_box([50,8,120],2);
        for(z=[20,40,80,100]) pin_hole(0,-78,z,8);
    }
}
module rail() {
    difference() {
        translate([-130,-50,0]) round_box([260,16,40],2);
        for(x=[-65,0,65]) for(z=[18,32]) pin_hole(x,-50,z,16);
    }
}
module holder() {
    difference() {
        union() {
            translate([-25,-34,0]) round_box([50,10,188],2);
            translate([-25,-25,0]) round_box([50,47,8],2);
            translate([0,10,0]) rotate([90,0,0]) soft_extrude(12,2)
                hull() {
                    translate([-25,0]) square([50,250]);
                    translate([0,255]) circle(r=25,$fn=48);
                }
        }
        for(z=[166,180]) pin_hole(0,-34,z,10);
    }
}
// gripは締結する部品の外面間距離。軸方向=+Y。
// 先端の二股を押し縮めて穴へ通し、肩が反対側で広がり抜け止めになる。
module lock_pin(grip=26) {
    translate([0,0,-4]) soft_extrude(8,0.45) round_profile(0.45)
        difference() {
            union() {
                translate([-8,-6]) square([16,6]);
                translate([-4,-0.5]) square([8,grip+6.5]);
                for(s=[-1,1]) scale([s,1]) polygon([
                    [3.5,grip+0.4], [5.2,grip+0.4],
                    [5.2,grip+1.4], [3.1,grip+6], [3.1,grip+0.4]
                ]);
            }
            translate([-1.2,grip-22]) square([2.4,32]);
            translate([0,grip-22]) circle(r=1.2);
        }
}
module coupon(gap=0.6) {
    difference() {
        translate([-13,0,0]) round_box([26,26,16],2);
        pin_hole(0,0,8,26,gap);
    }
}
module sole() {
    translate([0,5,0]) rotate([90,0,0]) linear_extrude(height=10)
        hull() { translate([0,60]) circle(r=60); translate([0,240]) circle(r=60); }
}
module shoe() {
    sole();
    difference() {
        translate([0,35,230]) scale([60,40,70]) sphere(r=1,$fn=40);
        translate([-65,-10,150]) cube([130,20,160]);
    }
}
module side(back=false) {
    if(back) mirror([0,1,0]) children(); else children();
}
module shoe_array(sole_only=false) {
    for(i=[0:1]) for(back=[false,true]) for(x=[-65,65])
        side(back) translate([x,50,40+i*pitch])
            if(sole_only) sole(); else shoe();
}
module hardware() {
    for(z=[36,56]) translate([0,-20,z]) lock_pin(40);
    for(z=[286,306,346,366]) translate([0,-18,z]) lock_pin(28);
    for(i=[0:1]) {
        for(z=[198,212]) translate([0,-26,z+i*pitch]) lock_pin(52);
        for(back=[false,true]) for(x=[-65,65]) for(z=[198,212])
            side(back) translate([x,10,z+i*pitch]) lock_pin(26);
    }
}
module frame() {
    translate([0,60,0]) base();
    for(i=[0:1]) {
        translate([0,60,16+i*pitch]) mast();
        for(back=[false,true]) side(back) {
            translate([0,60,180+i*pitch]) rail();
            for(x=[-65,65]) translate([x,60,32+i*pitch]) holder();
        }
        if(i==0) translate([0,60,266]) splice();
    }
}
module assembly(shoes=false) {
    color("#527387") frame();
    color("#d6a557") hardware();
    if(shoes) color("#d6a557") shoe_array();
}
if(part=="base") base();
else if(part=="mast") translate([0,0,70]) rotate([90,0,0]) mast();
else if(part=="splice") translate([0,0,78]) rotate([90,0,0]) splice();
else if(part=="rail") translate([0,0,50]) rotate([90,0,0]) rail();
else if(part=="holder") translate([0,0,25]) rotate([0,90,0]) holder();
else if(part=="pin26") translate([0,0,4]) lock_pin(26);
else if(part=="pin28") translate([0,0,4]) lock_pin(28);
else if(part=="pin40") translate([0,0,4]) lock_pin(40);
else if(part=="pin52") translate([0,0,4]) lock_pin(52);
else if(part=="coupon04") coupon(0.4);
else if(part=="coupon06") coupon(0.6);
else if(part=="coupon08") coupon(0.8);
else if(part=="shoes") shoe_array();
else if(part=="hardware") hardware();
else if(part=="frame") frame();
else if(part=="sole_interference") intersection() { assembly(); shoe_array(true); }
else if(part=="pin_interference") intersection() { frame(); hardware(); }
else if(part=="loaded") assembly(true);
else assembly();
