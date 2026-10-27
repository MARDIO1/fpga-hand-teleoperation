import sys,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from marker_display_control import DisplayController,select_candidates

def main():
    class MMIO:
        def __init__(self):self.array=np.zeros(0x10000//4,np.uint32);self.registers={0x18:0}
        def read(self,address):return self.registers.get(address,0)
        def write(self,address,value):self.registers[address]=value
    controller=DisplayController.__new__(DisplayController)
    controller.mmio=MMIO();controller.commit=0;controller.sequence=0
    point=dict(color='blue',u=100,v=100,area_px=300,bbox=[90,90,20,20])
    selected=dict(L=[point],R=[point]);pairs=[dict(left=0,right=0,id=1)]
    data=(selected,pairs,7,time.monotonic()*1000000,123,0,30.0,7.2)
    assert controller.publish(data,True)
    first=controller.mmio.array.copy();commit=controller.commit
    assert commit==7 and controller.mmio.read(0x10)==7
    assert not controller.publish(data,False)
    assert np.array_equal(first,controller.mmio.array)
    controller.mmio.registers[0x18]=commit
    assert controller.publish(data,False) and controller.commit==8
    # Old bank remains intact while the other bank is written.
    assert np.array_equal(first[0x600//4:0x800//4],controller.mmio.array[0x600//4:0x800//4])
    assert int(controller.mmio.array[0x400//4])==90|(90<<16)
    assert int(controller.mmio.array[0x410//4])==(90+640)|(90<<16)
    text=controller.mmio.array[0x1000//4:0x1500//4].astype('<u4').tobytes().decode('ascii')
    assert 'CAP FPS 30.0' in text and 'DET FPS 7.2' in text
    assert 'XYZ UNCAL' in text and 'P01 BLUE' in text and 'DELAYED DETECTIONS' in text
    spec=dict(min_width_px=8,max_width_px=70,min_height_px=8,max_height_px=70,max_aspect_ratio=2)
    good=dict(point,bbox=[1,1,48,24]);bad=dict(point,bbox=[1,1,49,24])
    assert select_candidates([good,bad],spec)==[good]
    print('DISPLAY CONTROL PASS inactive-bank writes, ack gating, coordinates, text, replaceable 2:1 selector')
if __name__=='__main__':main()
