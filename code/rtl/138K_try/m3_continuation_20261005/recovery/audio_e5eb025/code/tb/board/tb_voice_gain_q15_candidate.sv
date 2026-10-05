`timescale 1ns/1ps
module tb_voice_gain_q15_candidate;
    reg signed [15:0] wave_sample=0;
    reg [15:0] envelope=0;
    wire signed [15:0] sample_out;
    wire signed [23:0] pcm_out;
    voice_gain_q15_candidate dut(.*);
    integer fd,n,code,w,e,expected,checks=0;
    reg [2047:0] path;
    initial begin
        if(!$value$plusargs("VECTORS=%s",path))$fatal(1,"VECTORS required");
        fd=$fopen(path,"r");if(!fd)$fatal(1,"Cannot open vectors");
        while(!$feof(fd))begin
            code=$fscanf(fd,"%d %d %d\n",w,e,expected);
            if(code!=3)$fatal(1,"Malformed vector");
            wave_sample=w;envelope=e;#1;
            if($signed(sample_out)!==expected || $signed(pcm_out)!==(expected*256))
                $fatal(1,"gain wave=%0d env=%0d got=%0d expected=%0d pcm=%0d",w,e,$signed(sample_out),expected,$signed(pcm_out));
            checks++;
        end
        $fclose(fd);
        if(checks<300000)$fatal(1,"Insufficient coverage %0d",checks);
        $display("PASS voice_gain_q15_candidate vectors=%0d",checks);$finish;
    end
endmodule