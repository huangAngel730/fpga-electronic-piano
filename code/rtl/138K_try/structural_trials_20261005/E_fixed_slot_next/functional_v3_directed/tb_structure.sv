module tb_structure;
reg[31:0]p=0,expect_bits;reg parsed=0,keep=0,grant=0;reg[4:0]pi=0,gi=0;
wire[31:0]observed;structure_probe dut(p,parsed,pi,keep,grant,gi,observed);
integer fd,n=0,rc;
initial begin
fd=$fopen("transition_vectors.txt","r");if(!fd)$fatal(1,"missing vectors");
while(!$feof(fd))begin
rc=$fscanf(fd,"%h %h %h %h %h %h %h\n",p,parsed,pi,keep,grant,gi,expect_bits);
if(rc!=7)$fatal(1,"truncated vector");#1;
if(observed!==expect_bits)$fatal(1,"transition mismatch case=%0d",n);n++;
end
if(n!=303104)$fatal(1,"empty/truncated vector count");
$display("PASS transition oracle cases=%0d",n);$finish;end
endmodule
