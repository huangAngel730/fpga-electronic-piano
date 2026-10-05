module tb_structure;
reg[31:0]p=0;reg[4:0]rr=0,ix=0,expected_index;reg parsed=0,expected_valid;
reg[11:0]value_in=0,expected_value;wire v;wire[4:0]index_out;wire[11:0]value_out;
structure_probe dut(p,rr,parsed,ix,value_in,v,index_out,value_out);
integer fd,n=0,rc;
initial begin
fd=$fopen("selector_vectors.txt","r");if(!fd)$fatal(1,"missing vectors");
while(!$feof(fd))begin
rc=$fscanf(fd,"%h %h %h %h %h %h %h %h\n",p,rr,parsed,ix,value_in,expected_valid,expected_index,expected_value);
if(rc!=8)$fatal(1,"truncated vector");#1;
if(v!==expected_valid || (v && {index_out,value_out}!=={expected_index,expected_value}))
$fatal(1,"selector mismatch case=%0d",n);n++;
end
if(n!=274560)$fatal(1,"empty/truncated vector count");
$display("PASS selector oracle cases=%0d",n);$finish;end
endmodule
