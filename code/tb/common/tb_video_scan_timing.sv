`timescale 1ns/1ps
module tb_video_scan_timing;
    logic clk=0, rst_n=0;
    always #5 clk=~clk;
    wire [15:0] x,y,sx,sy;
    wire de,hs,vs,fs,ls,sde,shs,svs,sfs,sls;
    video_scan_timing candidate (.pixel_clk(clk),.rst_n(rst_n),
        .pixel_x(x),.pixel_y(y),.data_enable(de),.hsync(hs),.vsync(vs),
        .frame_start(fs),.line_start(ls));
    video_scan_timing #(.H_ACTIVE(4),.H_FRONT(1),.H_SYNC(2),.H_BACK(1),
        .V_ACTIVE(3),.V_FRONT(1),.V_SYNC(1),.V_BACK(1),
        .H_POLARITY(1),.V_POLARITY(1)) small_mode (
        .pixel_clk(clk),.rst_n(rst_n),.pixel_x(sx),.pixel_y(sy),
        .data_enable(sde),.hsync(shs),.vsync(svs),.frame_start(sfs),.line_start(sls));
    integer lit=0, lines=0, frames=0, hpulses=0, vpulses=0;
    task automatic verify(input integer cycle);
        integer ex,ey,tx,ty;
        ex=cycle%800; ey=(cycle/800)%525;
        tx=cycle%8; ty=(cycle/8)%6;
        if(x!==ex || y!==ey || de!==(ex<640 && ey<480) ||
            hs!==(!(ex>=656 && ex<752)) || vs!==(!(ey>=490 && ey<492)) ||
            fs!==(ex==0 && ey==0) || ls!==(ex==0))
            $fatal(1,"candidate raster mismatch at pixel %0d",cycle);
        if(sx!==tx || sy!==ty || sde!==(tx<4 && ty<3) ||
            shs!==(tx>=5 && tx<7) || svs!==(ty==4) ||
            sfs!==(tx==0 && ty==0) || sls!==(tx==0))
            $fatal(1,"parameter/polarity mismatch at pixel %0d",cycle);
    endtask
    initial begin
        #2;
        if(de || fs || ls || hs!==1 || vs!==1 || shs!==0 || svs!==0)
            $fatal(1,"reset blanking/polarity failure");
        @(negedge clk); rst_n=1; #1;
        for(integer cycle=0; cycle<840000; cycle=cycle+1) begin
            verify(cycle);
            lit=lit+de; lines=lines+ls; frames=frames+fs;
            hpulses=hpulses+!hs; vpulses=vpulses+!vs;
            @(posedge clk); #1;
        end
        if(lit!=614400 || lines!=1050 || frames!=2 ||
            hpulses!=100800 || vpulses!=3200)
            $fatal(1,"frame geometry totals mismatch");
        @(negedge clk); rst_n=0; #1;
        if(x || y || de || fs || ls) $fatal(1,"mid-frame reset failure");
        @(negedge clk); rst_n=1; #1; verify(0);
        $display("PASS video_scan_timing: 2 full frames + parameter/polarity + reset");
        $finish;
    end
    initial begin #9000000; $fatal(1,"raster timeout"); end
endmodule
