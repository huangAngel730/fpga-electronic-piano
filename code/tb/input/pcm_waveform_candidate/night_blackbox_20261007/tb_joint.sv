`timescale 1ns/1ps
// Only public ports. Mutations affect this NEW connection wrapper, not RTL.
module tb_joint;
    parameter integer MUTATION=0;
    parameter [31:0] FIRST_SEQ=0;
    reg ac=0,pc=0,arun=1,prun=1,arst=1,drst=1,load=0;
    reg signed [23:0] left=0,right=0;
    always #12.5 if(arun) ac=~ac; else ac=0;
    initial begin #7; forever begin #20; if(prun) pc=~pc; else pc=0; end end
    wire wrst,restart,valid,ov,enq,dropped,sdone,pdone;
    wire [31:0] seq,oseq,dc;
    wire signed [23:0] sl,sr,ol,orr;
    wire [15:0] level;
    pcm_waveform_observer_bridge #(.DEPTH(32),.FIRST_SEQ(FIRST_SEQ)) bridge (
        .audio_clk(ac),.pixel_clk(pc),.audio_rst_n(arst),.display_rst_n(drst),
        .audio_frame_load(load),.audio_play_left(left),.audio_play_right(right),
        .waveform_rst_n(wrst),.stream_restart(restart),.sample_valid(valid),
        .sample_seq(seq),.sample_left(sl),.sample_right(sr),
        .observed_valid(ov),.observed_seq(oseq),.observed_left(ol),.observed_right(orr),
        .observation_enqueued(enq),.observation_dropped(dropped),.observation_queue_level(level),
        .observation_drop_count(dc),.source_reset_done(sdone),.pixel_reset_done(pdone));
    wire [31:0] linked_seq = (MUTATION==2 && seq[7:0]==8'hff) ? seq+32'd1 : seq;
    wire signed [23:0] linked_left=(MUTATION==1)?sr:sl;
    reg [15:0] x=0,y=0;
    wire de=(x<640 && y<480);
    wire fs=(x==0 && y==0);
    reg enable=1;
    wire mask,tv; wire [7:0] r,g,b; wire [31:0] gap,drop;
    pcm_waveform_candidate wave(.pixel_clk(pc),.pixel_rst_n(wrst),.sample_valid(valid),
        .sample_seq(linked_seq),.sample_left(linked_left),.sample_right(sr),.stream_restart(restart),
        .pixel_x(x),.pixel_y(y),.data_enable(de),.frame_start(fs),.waveform_enable(enable),
        .waveform_mask(mask),.waveform_r(r),.waveform_g(g),.waveform_b(b),.trace_valid(tv),
        .display_gap_count(gap),.window_drop_count(drop));

    integer fd,vf,ret,index,a,bb,interval,vector_index,count,frames_wanted;
    integer cyc=0,frame=0,scan_pixels=0,errors=0,state_errors=0;
    integer branch=0,aepoch=0,loads=0,observations=0,deliveries=0,restarts=0,full_rows=0;
    reg [31:0] ordinal=FIRST_SEQ;
    reg [31:0] hash=5381;
    string capture_path,vector_path,mode;
    // Full signed24 2048 samples, mathematical reference independent of banks.
    integer samples[0:2047],pending_lo[0:511],pending_hi[0:511],front_lo[0:511],front_hi[0:511];
    integer used=0,i,j,lo,hi;
    reg pending=0,front=0,seen=0;
    reg [31:0] previous=0,egap=0,edrop=0;
    reg [24:0] p0=0,p1=0,p2=0,now_pixel;
    function [31:0] inc(input [31:0] n); inc=(&n)?n:n+1; endfunction
    always @(posedge ac) if(fd) begin
        if(arst && load) begin
            $fdisplay(fd,"A %0t %0d %0d %0d %0d %0d %0d",$time,branch,aepoch,loads,ordinal,left,right);
            ordinal=ordinal+1;loads=loads+1;
        end
        if(arst && ov) begin
            $fdisplay(fd,"O %0t %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",$time,branch,aepoch,oseq,ol,orr,enq,dropped,level,dc,sdone);
            observations=observations+1;
        end
    end
    always @(negedge wrst) if(fd) $fdisplay(fd,"Z %0t %0d %0d %0d",$time,cyc,branch,aepoch);
    always @(posedge pc) if(fd) begin
        cyc=cyc+1;
        if(!wrst) begin
            used=0;pending=0;front=0;seen=0;egap=0;edrop=0;p0=0;p1=0;p2=0;
            $fdisplay(fd,"R %0d",cyc);
        end else begin
            if(restart) begin
                used=0;pending=0;front=0;seen=0;restarts=restarts+1;
                $fdisplay(fd,"T %0d %0d",cyc,branch);
            end else if(fs && pending) begin
                for(i=0;i<512;i=i+1) begin front_lo[i]=pending_lo[i];front_hi[i]=pending_hi[i];end
                pending=0;front=1;
            end
            if(valid) begin
                deliveries=deliveries+1;
                $fdisplay(fd,"D %0d %0t %0d %0d %0d %0d %0d %0d",cyc,$time,branch,aepoch,seq,sl,sr,restart);
                if(!restart) begin
                    if(seen && seq!=previous+32'd1) begin used=0;egap=inc(egap);end
                    seen=1;previous=seq;samples[used]=$signed(sl);used=used+1;
                    if(used==2048) begin
                        if(pending) edrop=inc(edrop);
                        for(i=0;i<512;i=i+1) begin
                            lo=samples[4*i];hi=lo;
                            for(j=1;j<4;j=j+1) begin
                                if(samples[4*i+j]<lo)lo=samples[4*i+j];
                                if(samples[4*i+j]>hi)hi=samples[4*i+j];
                            end
                            pending_lo[i]=lo;pending_hi[i]=hi;
                        end
                        used=0;pending=1;
                    end
                end
            end
            now_pixel=0;
            if(enable && de && x>=64 && x<=575 && y>=64 && y<=319) begin
                now_pixel={1'b1,24'h081020};
                if(y==191)now_pixel={1'b1,24'h404040};
                lo=front_lo[x-64]>>>16;hi=front_hi[x-64]>>>16;
                if(front && !restart && $signed({1'b0,y})>=191-hi && $signed({1'b0,y})<=191-lo)now_pixel={1'b1,24'h00e0ff};
            end
            p2=p1;p1=p0;p0=now_pixel;
        end
        if(fs) $fdisplay(fd,"F %0d %0d %0d %0d %0d",cyc,frame,enable,wrst,front);
        #1;
        if({mask,r,g,b}!==p2) begin errors=errors+1;if(errors<=12)$fdisplay(fd,"BAD_PIXEL %0d %0d %0d %h %h",cyc,x,y,{mask,r,g,b},p2);end
        if(tv!==front || gap!==egap || drop!==edrop) begin state_errors=state_errors+1;if(state_errors<=12)$fdisplay(fd,"BAD_STATE %0d %0d %0d %0d %0d %0d %0d",cyc,tv,front,gap,egap,drop,edrop);end
        scan_pixels=scan_pixels+1;hash=(hash*33)^{mask,r,g,b};
        if(x==799)begin $fdisplay(fd,"L %0d %0d %0d %0d",cyc,frame,y,hash);hash=5381;full_rows=full_rows+1;end
        if(fs) $fdisplay(fd,"S %0d %0d %0d %0d",cyc,tv,gap,drop);
    end
    // Scanner is independent of observation reset; only pixel clock stop pauses.
    always @(negedge pc) if(fd) begin
        if(x==799)begin x=0;if(y==524)begin y=0;frame=frame+1;end else y=y+1;end
        else x=x+1;
    end
    task reset_branch(input integer kind);
        begin
            branch=branch+1;$fdisplay(fd,"B %0t %0d %0d",$time,branch,kind);
            if(kind==2)begin aepoch=aepoch+1;ordinal=FIRST_SEQ;arst=0;end else drst=0;
            repeat(12)@(negedge ac);
            if(kind==2)arst=1;else drst=1;
        end
    endtask
    initial begin #550000000;$fatal(1,"SIMULATION_DEADLINE");end
    initial begin
        // Explicit assertion edge before either clock; no initial X reset.
        #1;arst=0;drst=0;
        if(!$value$plusargs("CAPTURE=%s",capture_path)||!$value$plusargs("VECTORS=%s",vector_path)||!$value$plusargs("MODE=%s",mode)||!$value$plusargs("COUNT=%d",count)||!$value$plusargs("FRAMES=%d",frames_wanted))$fatal(1,"ARGS");
        fd=$fopen(capture_path,"w");vf=$fopen(vector_path,"r");if(!fd||!vf)$fatal(1,"FILES");
        $fdisplay(fd,"HEADER JOINT 1 %s %0d %0d %0d",mode,FIRST_SEQ,count,frames_wanted);
        repeat(8)@(negedge ac);arst=1;drst=1;repeat(20)@(negedge ac);
        for(index=0;index<count;index=index+1)begin
            ret=$fscanf(vf,"%d %d %d %d\n",vector_index,a,bb,interval);
            if(ret!=4 || vector_index!=index || interval<1)$fatal(1,"VECTOR");
            if(mode=="stress")begin
                if(index==2100)begin prun=0;$fdisplay(fd,"C %0t pixel_stop",$time);end
                if(index==2220)begin prun=1;$fdisplay(fd,"C %0t pixel_resume",$time);end
                if(index==4800)begin prun=0;$fdisplay(fd,"C %0t pixel_stop_reset",$time);reset_branch(1);end
                if(index==4900)begin prun=1;$fdisplay(fd,"C %0t pixel_resume_reset",$time);end
                if(index==7300)begin arun=0;$fdisplay(fd,"C %0t audio_stop",$time);#700000;arun=1;$fdisplay(fd,"C %0t audio_resume",$time);@(negedge ac);end
                if(index==7500)reset_branch(2);
            end
            left=a;right=bb;load=1;@(negedge ac);load=0;
            repeat(interval-1)@(negedge ac);
        end
        $fclose(vf);prun=1;arun=1;
        wait(frame>=frames_wanted);@(negedge pc);
        $fdisplay(fd,"FINAL %0d %0d %0d %0d %0d",cyc,tv,gap,drop,dc);
        $fdisplay(fd,"END %0d %0d %0d %0d %0d %0d %0d %0d",cyc,scan_pixels,errors,state_errors,loads,observations,deliveries,full_rows);
        $fclose(fd);fd=0;
        $display("COMPLETE JOINT mode=%s pixels=%0d errors=%0d state_errors=%0d",mode,scan_pixels,errors,state_errors);$finish;
    end
endmodule
