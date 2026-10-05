`timescale 1ns/1ps
module tb_mask_selector;
logic[31:0]pending;logic[4:0]rr,ix,li;logic active,locked;
logic[11:0]val,held;logic[15:0]cool;logic[3:0]q;
logic discrete,ready,burst;wire valid;wire[4:0]idx;wire[11:0]value;
wire[31:0]mask,nxt;wire grant;
exact_mask_selector dut(pending,rr,ix,li,active,locked,val,held,cool,q,discrete,ready,burst,valid,idx,value,mask,grant,nxt);
integer fd,r,n=0,processed=0,a,b,c,d,e,f,g,h,i,j,k,l,m,o,pg;
reg[31:0]pp,sm,pn;
string vector_path="mask_vectors.txt";
initial begin
if($value$plusargs("VECTORS=%s",vector_path))begin end
fd=$fopen(vector_path,"r");if(!fd)$fatal(1,"missing vectors");
while(!$feof(fd))begin
r=$fscanf(fd,"%h %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %h %d %h\n",pp,a,b,c,d,e,f,g,h,i,j,k,l,m,o,pg,sm,n,pn);
if(r==19)begin
pending=pp;rr=5'(a);ix=5'(b);li=5'(c);active=1'(d);locked=1'(e);
val=12'(f);held=12'(g);cool=16'(h);q=4'(i);discrete=1'(j);ready=1'(k);burst=1'(l);
#2;processed++;
if({valid,idx,value,mask,grant,nxt}!=={1'(m),5'(o),12'(pg),sm,1'(n),pn})$fatal(1,"mask+pending independent oracle mismatch RR=%0d ix=%0d got mask=%h pending=%h expected mask=%h pending=%h",a,b,mask,nxt,sm,pn);
end else if(r!=-1)$fatal(1,"malformed vector");
end
if(processed!=399360)$fatal(1,"mask oracle empty/truncated case count=%0d",processed);
$display("PASS mask/next-pending independent cases=%0d",processed);$finish;
end
initial begin #10000000;$fatal(1,"timeout");end
endmodule
