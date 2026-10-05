`timescale 1ns/1ps
module tb_pcm_mixer_4voice;
    logic [95:0] voices_left, voices_right;
    wire signed [23:0] mixed_left, mixed_right;
    wire clip_left, clip_right, clip_any;
    pcm_mixer_4voice dut (.*);
    logic [23:0] v0l,v1l,v2l,v3l,v0r,v1r,v2r,v3r;
    logic [23:0] expected_left, expected_right;
    integer expected_cl, expected_cr, expected_any;
    integer fd, got, frame = 0;
    string filename;
    initial begin
        if (!$value$plusargs("vectors=%s",filename))
            $fatal(1,"missing +vectors=<reference-file>");
        fd=$fopen(filename,"r");
        if(fd==0) $fatal(1,"cannot open reference file");
        forever begin
            got=$fscanf(fd,
                "%h %h %h %h %h %h %h %h %h %h %d %d %d\n",
                v0l,v1l,v2l,v3l,v0r,v1r,v2r,v3r,
                expected_left,expected_right,expected_cl,expected_cr,expected_any);
            if(got==-1) break;
            if(got!=13) $fatal(1,"bad reference frame %0d fields=%0d",frame,got);
            voices_left={v3l,v2l,v1l,v0l};
            voices_right={v3r,v2r,v1r,v0r};
            #1;
            if(mixed_left !== expected_left || mixed_right !== expected_right ||
               clip_left !== (expected_cl!=0) ||
               clip_right !== (expected_cr!=0) ||
               clip_any !== (expected_any!=0))
                $fatal(1,"frame %0d: left %h/%h right %h/%h clip %b%b%b vs %0d%0d%0d",
                    frame,mixed_left,expected_left,mixed_right,expected_right,
                    clip_left,clip_right,clip_any,expected_cl,expected_cr,expected_any);
            frame=frame+1;
        end
        $fclose(fd);
        if(frame!=3008) $fatal(1,"expected 3008 compared frames, got %0d",frame);
        $display("PASS mixer: %0d stereo frames versus M1 Python golden model",frame);
        $finish;
    end
    initial begin #100000; $fatal(1,"mixer timeout"); end
endmodule
