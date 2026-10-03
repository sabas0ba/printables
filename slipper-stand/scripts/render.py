"""実際のSTLから正投影と斜め表示を生成する。"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from build import vertices, OUT


def mesh(name, color):
    triangles = np.array(vertices(OUT/f'{name}.stl')).reshape(-1,3,3)
    normals = np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    norms = np.linalg.norm(normals,axis=1)
    shade = .68+.32*np.abs(normals @ np.array([.3,.7,.6]))/np.maximum(norms,1e-8)
    rgb = np.array(matplotlib.colors.to_rgb(color))
    return triangles, np.column_stack([shade[:,None]*rgb, np.ones(len(shade))])


fig=plt.figure(figsize=(14,8),facecolor='#f3f5f7')
fig.suptitle('SLIPPER STAND / TOOL-FREE / V03',fontsize=23,fontweight='bold',y=.96)
for index,loaded,angle,title in [(1,True,90,'FRONT / 2 PAIRS'),
                               (2,True,0,'SIDE / SOLES FACE INWARD'),
                               (3,False,45,'FRAME / 4 PAIRS TOTAL')]:
    ax=fig.add_subplot(1,3,index,projection='3d')
    ax.set_facecolor('#f3f5f7')
    items=[mesh('frame','#527387'),mesh('hardware','#d6a557')]
    if loaded:
        items.append(mesh('shoes','#d8a267'))
    triangles=np.concatenate([item[0] for item in items])
    colors=np.concatenate([item[1] for item in items])
    ax.add_collection3d(Poly3DCollection(triangles,facecolors=colors,linewidth=0,antialiased=False))
    ax.set(xlim=(-150,150),ylim=(-135,135),zlim=(0,675))
    ax.set_box_aspect((300,270,675))
    ax.set_proj_type('ortho')
    ax.view_init(elev=0 if loaded else 14,azim=angle)
    ax.set_axis_off()
    ax.set_title(title,fontsize=13,pad=10)
fig.text(.07,.09,'Footprint: 280 x 250 mm     Frame: 636 mm     Loaded envelope: 650 mm',fontsize=14)
fig.text(.07,.035,'Printed locking pins shown in gold. Rounded edges. Physical fit / retention / stability unverified.',fontsize=10,color='#596673')
fig.subplots_adjust(left=.02,right=.98,top=.84,bottom=.18,wspace=.01)
fig.savefig(OUT/'preview.png',dpi=150,facecolor=fig.get_facecolor())

fig=plt.figure(figsize=(14,6),facecolor='#f3f5f7')
fig.suptitle('ROUNDED HOLDER + PRINTED LOCKING PIN',fontsize=21,fontweight='bold',y=.95)
for index,name,color,title in [(1,'holder','#527387','HOLDER / R2 EDGES'),
                               (2,'pin26','#d6a557','PIN / SPLIT RELEASE TIP'),
                               (3,'coupon06','#527387','FIT COUPON / 0.6 mm CLEARANCE')]:
    ax=fig.add_subplot(1,3,index,projection='3d')
    ax.set_facecolor('#f3f5f7')
    triangles,colors=mesh(name,color)
    ax.add_collection3d(Poly3DCollection(triangles,facecolors=colors,linewidth=0,antialiased=False))
    points=triangles.reshape(-1,3)
    low=points.min(axis=0)
    high=points.max(axis=0)
    ax.set(xlim=(low[0]-2,high[0]+2),ylim=(low[1]-2,high[1]+2),zlim=(low[2]-2,high[2]+2))
    ax.set_box_aspect(high-low+4)
    ax.set_proj_type('ortho')
    ax.view_init(elev=28,azim=-55)
    ax.set_axis_off()
    ax.set_title(title,fontsize=12)
fig.text(.08,.07,'Print pin26 + coupon06 first. Insert split tip first; pinch it to release. No screws or glue.',fontsize=12)
fig.subplots_adjust(left=.02,right=.98,top=.82,bottom=.16,wspace=.04)
fig.savefig(OUT/'details.png',dpi=150,facecolor=fig.get_facecolor())
