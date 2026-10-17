`timescale 1ns/1ps
module tb_waveform;
    reg clk=0; always #20 clk=~clk;
    reg rst=0, sv=0, restart=0, de=0, fs=0, en=0;
    reg [31:0] seq=0;
    reg signed [23:0] left=0,right=0;
    reg [15:0] x=0,y=0;
    wire mask,tvalid; wire [7:0] r,g,b; wire [31:0] gaps,drops;
    pcm_waveform_candidate dut(clk,rst,sv,seq,left,right,restart,x,y,de,fs,en,
        mask,r,g,b,tvalid,gaps,drops);
    // Independent oracle: full unquantized signed24 windows; no DUT hierarchy,
    // no RAM bank identities and no dependence on the implementation pipeline.
    integer samples[0:2047];
    integer pending_lo[0:511],pending_hi[0:511];
    integer front_lo[0:511],front_hi[0:511];
    integer used=0;
    reg pending=0,front=0,seen=0;
    reg [31:0] previous,egap=0,edrop=0;
    reg [24:0] pipe0=0,pipe1=0,pipe2=0,now_pixel;
    integer checks=0,pixel_errors=0,state_errors=0,frame=0,cycle=0;
    integer capture,vector_file,normal_file,rc,n,flags,tx,ty,a,bb,i,j,lo,hi;
    reg [31:0] ts;
    reg [31:0] hash_actual=5381,hash_expected=5381;
    reg [15:0] ox0,oy0,ox1,oy1,ox2,oy2;
    integer of0=-1,of1=-1,of2=-1;
    reg [1023:0] vectors_path,normal_path,capture_path;
    function [31:0] inc;
        input [31:0] z; begin inc=(&z)?z:z+1; end
    endfunction
    task tick;
        input integer scan_frame;
        begin
            @(posedge clk);
            cycle=cycle+1;
            // Input pre-edge semantics: publish OLD pending, then ingest.
            if (!rst) begin
                used=0;pending=0;front=0;seen=0;egap=0;edrop=0;
                pipe0=0;pipe1=0;pipe2=0;of0=-1;of1=-1;of2=-1;
                $fdisplay(capture,"R %0d",cycle);
            end else begin
                if(restart) begin
                    used=0;pending=0;front=0;seen=0;
                    $fdisplay(capture,"T %0d",cycle);
                end else if(fs && pending) begin
                    for(i=0;i<512;i=i+1)begin
                        front_lo[i]=pending_lo[i];front_hi[i]=pending_hi[i];
                    end
                    front=1;pending=0;
                end
                if(fs) $fdisplay(capture,"V %0d %0d",cycle,scan_frame);
                if(sv) $fdisplay(capture,"I %0d %0d %0d %0d %0d",cycle,seq,left,right,restart);
                if(sv && !restart)begin
                    if(seen && seq != previous+32'd1)begin used=0;egap=inc(egap);end
                    seen=1;previous=seq;samples[used]=$signed(left);used=used+1;
                    if(used==2048)begin
                        if(pending)edrop=inc(edrop);
                        for(i=0;i<512;i=i+1)begin
                            lo=samples[4*i];hi=lo;
                            for(j=1;j<4;j=j+1)begin
                                if(samples[4*i+j]<lo)lo=samples[4*i+j];
                                if(samples[4*i+j]>hi)hi=samples[4*i+j];
                            end
                            pending_lo[i]=lo;pending_hi[i]=hi;
                        end
                        used=0;pending=1;
                    end
                end
                now_pixel=0;
                if(de && en && x>=64 && x<=575 && y>=64 && y<=319)begin
                    now_pixel={1'b1,24'h081020};
                    if(y==191)now_pixel={1'b1,24'h404040};
                    // On the current edge, an already published front snapshot
                    // is immutable. Restart invalidates it immediately.
                    // Evaluate shifts as signed integers BEFORE comparison;
                    // unsigned pixel_y must not change the shift context.
                    lo=front_lo[x-64]>>>16;hi=front_hi[x-64]>>>16;
                    if(front && !restart && $signed({1'b0,y})>=191-hi &&
                        $signed({1'b0,y})<=191-lo)now_pixel={1'b1,24'h00e0ff};
                end
                pipe2=pipe1;pipe1=pipe0;pipe0=now_pixel;
                ox2=ox1;oy2=oy1;of2=of1;
                ox1=ox0;oy1=oy0;of1=of0;
                ox0=x;oy0=y;of0=scan_frame;
            end
            #1;
            checks=checks+1;
            if({mask,r,g,b} !== pipe2)begin
                pixel_errors=pixel_errors+1;
                if(pixel_errors<=8)$fdisplay(capture,"ERROR_PIXEL %0d %0d %0d %h %h",cycle,ox2,oy2,{mask,r,g,b},pipe2);
            end
            if(tvalid !== front || gaps !== egap || drops !== edrop)begin
                state_errors=state_errors+1;
                if(state_errors<=8)$fdisplay(capture,"ERROR_STATE %0d %0d %0d %0d %0d %0d %0d",cycle,tvalid,front,gaps,egap,drops,edrop);
            end
            if(of2>=0)begin
                hash_actual=(hash_actual*33)^{mask,r,g,b};
                hash_expected=(hash_expected*33)^pipe2;
                if(ox2==799)begin
                    $fdisplay(capture,"L %0d %0d %0d %0d",of2,oy2,hash_actual,hash_expected);
                    hash_actual=5381;hash_expected=5381;
                end
            end
            @(negedge clk);
        end
    endtask
    initial begin
        if(!$value$plusargs("vectors=%s",vectors_path) ||
           !$value$plusargs("normal=%s",normal_path) ||
           !$value$plusargs("capture=%s",capture_path))$fatal(1,"PATHS");
        capture=$fopen(capture_path,"w");
        vector_file=$fopen(vectors_path,"r");
        normal_file=$fopen(normal_path,"r");
        if(!capture || !vector_file || !normal_file)$fatal(1,"FILES");
        $fdisplay(capture,"HEADER T058 1");
        @(negedge clk);
        while(!$feof(vector_file))begin
            rc=$fscanf(vector_file,"%d %d %d %d %d %d\n",flags,tx,ty,ts,a,bb);
            if(rc!=6)$fatal(1,"VECTOR_PARSE");
            rst=flags[0];restart=flags[1];fs=flags[2];sv=flags[3];de=flags[4];en=flags[5];
            x=tx;y=ty;seq=ts;left=a;right=bb;tick(-1);
        end
        // Clear directed epoch, then replay every sealed A record exactly once.
        rst=0;sv=0;restart=0;fs=0;en=1;de=0;tick(-1);rst=1;
        n=0;
        for(frame=0;frame<8;frame=frame+1)begin
            for(ty=0;ty<525;ty=ty+1)begin
                for(tx=0;tx<800;tx=tx+1)begin
                    x=tx;y=ty;de=(tx<640 && ty<480);fs=(tx==0 && ty==0);
                    en=(frame!=7);sv=0;
                    if(((frame*420000+ty*800+tx)%500)==200 && n<5849)begin
                        rc=$fscanf(normal_file,"%d %d %d\n",ts,a,bb);
                        if(rc!=3)$fatal(1,"NORMAL_PARSE");
                        seq=ts;left=a;right=bb;sv=1;n=n+1;
                    end
                    tick(frame);
                end
            end
        end
        sv=0;fs=0;de=0;tick(-1);tick(-1);tick(-1);
        $fdisplay(capture,"END %0d %0d %0d %0d %0d %0d %0d",checks,pixel_errors,state_errors,n,8,gaps,drops);
        $fclose(capture);$display("SIM_DONE T058 checks=%0d pixel_errors=%0d state_errors=%0d",checks,pixel_errors,state_errors);
        $finish;
    end
endmodule
