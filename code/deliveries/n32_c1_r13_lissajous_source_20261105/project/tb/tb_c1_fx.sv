`timescale 1ns/1ps
module tb_c1_fx;
    logic clk=0;
    always #5 clk=~clk;
    logic rst_n=0,cancel=0,frame_tick=0,valid=0,ready_out=1;
    logic [31:0] id=0;
    logic [2:0] mode=0;
    logic [2:0] timbre=0;
    logic signed [31:0] piano=0,organ=0;
    logic signed [23:0] snare=0,sax=0,guitar=0;
    wire ready_in,out_valid;
    wire [31:0] out_id;
    wire signed [23:0] left,right;
    wire [7:0] clip_bits;
    c1_pcm_effects dut(
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.frame_tick(frame_tick),
        .current_req_id(id),.input_valid(valid),.input_ready(ready_in),.input_id(id),
        .requested_mode(mode),.requested_timbre(timbre),.piano(piano),.organ(organ),
        .snare(snare),.sax(sax),.guitar(guitar),.upstream_clip(1'b0),
        .result_valid(out_valid),.result_ready(ready_out),.result_id(out_id),
        .left(left),.right(right),.clip_bits(clip_bits),.busy());
`ifdef C1_R04_COMPARE
    wire ref_valid,ref_ready;
    wire [31:0] ref_id;
    wire signed [23:0] ref_left,ref_right;
    wire [7:0] ref_clip;
    integer compared=0;
    r04_c1_pcm_effects reference(
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.frame_tick(frame_tick),
        .current_req_id(id),.input_valid(valid),.input_ready(ref_ready),.input_id(id),
        .requested_mode(mode),.requested_timbre(timbre),.piano(piano),.organ(organ),
        .snare(snare),.sax(sax),.guitar(guitar),.upstream_clip(1'b0),
        .result_valid(ref_valid),.result_ready(out_valid && ready_out),.result_id(ref_id),
        .left(ref_left),.right(ref_right),.clip_bits(ref_clip),.busy());
    always @(posedge clk) if(rst_n) begin
        if(valid && ready_in && !ref_ready) $fatal(1,"R04 refused shared stimulus");
        if(out_valid && ready_out) begin
            if(!ref_valid || {out_id,left,right,clip_bits} !== {ref_id,ref_left,ref_right,ref_clip})
                $fatal(1,"R04/R05 mismatch id=%0d mode=%0d ref=%0d,%0d,%h got=%0d,%0d,%h",
                    id,mode,ref_left,ref_right,ref_clip,left,right,clip_bits);
            compared++;
        end
    end
`endif
    task automatic send(input integer p=0,o=0,n=0,s=0,g=0);
        integer age;
        @(negedge clk);
        if(!ready_in) $fatal(1,"input not ready");
        id++; piano=p;organ=o;snare=n;sax=s;guitar=g;valid=1;
        @(negedge clk); valid=0;
        age=0;
        while(!out_valid && age<64) begin @(negedge clk); age++; end
        if(!out_valid || out_id!=id) $fatal(1,"missing/wrong FX frame %0d",id);
    endtask
    task automatic check_pcm(input integer value);
        if(left!==24'(value) || right!==24'(value))
            $fatal(1,"expected %0d got %0d %0d at %0d",value,left,right,id);
    endtask
    task automatic reset_fx(input logic [2:0] new_mode,input logic [2:0] new_timbre);
        @(negedge clk); rst_n=0;
        @(negedge clk); mode=new_mode;timbre=new_timbre;rst_n=1;
    endtask
    task automatic send_isolated(input integer voice, selected_sample, other_sample);
        integer other_voice;
        integer lanes[5];
        other_voice=(voice+1)%5;
        foreach(lanes[i])
            lanes[i]=(i==voice) ? selected_sample : (i==other_voice ? other_sample : 0);
        send(lanes[0],lanes[1],lanes[2],lanes[3],lanes[4]);
    endtask
    integer previous, chorus_seen=0,reverb_seen=0;
    integer wet_frames;
    integer random_seed=20261104;
    initial begin
        repeat(3) @(negedge clk);
        rst_n=1;
        repeat(128) send();
        send(320000,10000); check_pcm(160000);
        for(integer n=1;n<=28800;n++) begin
            send(0,10000);
            case(n)
                14400:check_pcm(160000);
                28800:check_pcm(40000);
                default:check_pcm(0);
            endcase
        end
        // A K2 change fades out the old private send then invalidates its memory.
        timbre=1;
        repeat(257) send();
        send(10000,-320000); check_pcm(-160000);
        for(integer n=1;n<=14400;n++) begin
            send(10000);
            if(n==14400) check_pcm(-160000);
            else check_pcm(0);
        end
        // Test K1 mode transition under a constant input with no private tail.
        timbre=2;
        repeat(257) send();
        send(0,0,320000); previous=int'(left);
        mode=1;
        for(integer n=0;n<257;n++) begin
            send(0,0,320000);
            if($signed(left)-previous>2500 || previous-$signed(left)>2500)
                $fatal(1,"hard mode switch");
            previous=int'(left);
        end
        check_pcm(320000);
        for(integer n=0;n<1400;n++) begin
            send(5000,0,320000);
            if(left!=320000 || right!=320000) chorus_seen++;
        end
        if(chorus_seen==0) $fatal(1,"chorus did not contribute");
        @(negedge clk); rst_n=0;
        @(negedge clk); rst_n=1; mode=2;
        repeat(260) send();
        send(20000,40000,60000,80000,100000); check_pcm(300000);
        for(integer n=0;n<5200;n++) begin
            send();
            if(left!=0 || right!=0) reverb_seen++;
        end
        if(reverb_seen==0) $fatal(1,"ensemble reverb has no tail");
        send(5000000,5000000,5000000,5000000,5000000);
        if(left!=24'sh7fffff || clip_bits[3:2]!=2'b11) $fatal(1,"mix clipping");
        // Kill an accepted ID, then ensure the next frame may complete.
        @(negedge clk); id++; valid=1;
        @(negedge clk); valid=0; frame_tick=1;
        @(negedge clk); frame_tick=0;
        repeat(64) begin @(negedge clk); if(out_valid) $fatal(1,"canceled ID escaped"); end
        send();
        @(negedge clk); rst_n=0;
        @(negedge clk); rst_n=1; mode=0;timbre=0;
        send(); check_pcm(0);
        // Sweep all five send groups through each mode with a separate dry
        // reference on an unselected group. Shared reverb uses all sources.
        for(integer voice=0;voice<5;voice++) begin
            reset_fx(0,3'(voice));
            repeat(260) begin send_isolated(voice,0,10000); check_pcm(0); end
            send_isolated(voice,320000,10000); check_pcm(160000);
            for(integer n=1;n<=14400;n++) begin
                send_isolated(voice,0,10000);
                if(n==14400) check_pcm(160000);
                else check_pcm(0);
            end

            reset_fx(1,3'(voice));
            repeat(260) send();
            repeat(1100) begin
                send_isolated(voice,0,10000); check_pcm(0);
            end
            send_isolated(voice,320000,10000); check_pcm(320000);
            wet_frames=0;
            repeat(1100) begin
                send_isolated(voice,0,10000);
                if(left!=0 || right!=0) wet_frames++;
            end
            if(wet_frames==0) $fatal(1,"missing isolated chorus, stem %d",voice);

            reset_fx(2,3'((voice+1)%5));
            repeat(260) send();
            send_isolated(voice,320000,0); check_pcm(320000);
            wet_frames=0;
            repeat(2000) begin
                send();
                if(left!=0 || right!=0) wet_frames++;
            end
            if(wet_frames==0) $fatal(1,"missing shared reverb, stem %d",voice);
        end
        // Solo reverb rejects all four other stems even after a full ring.
        for(integer voice=0;voice<5;voice++) begin
            reset_fx(3,3'(voice));
            repeat(2100) begin send_isolated(voice,0,50000); check_pcm(0); end
            send_isolated(voice,320000,50000); check_pcm(320000);
            for(integer sample_index=1;sample_index<=1499;sample_index++)
                send_isolated(voice,0,50000);
            check_pcm(14000);
            timbre=3'((voice+2)%5);
            repeat(2200) begin send(); end
            check_pcm(0);
        end
        reset_fx(4,0);
        repeat(260) send();
        send(20000,40000,60000,80000,100000); check_pcm(20000);
        repeat(2100) begin send(); check_pcm(0); end
        $display("PASS R11_FX_REVERB_AND_DRY");
        for(integer solo_mode=0;solo_mode<2;solo_mode++) begin
            reset_fx(2'(solo_mode),0);
            repeat(260) begin
                send(0,0,25000,50000,100000);
                check_pcm(0);
            end
            timbre=1;
            repeat(257) begin
                send(0,0,25000,50000,100000);
                check_pcm(0);
            end
            mode=2'(1-solo_mode);
            repeat(257) begin
                send(0,0,25000,50000,100000);
                check_pcm(0);
            end
        end
`ifdef C1_R04_COMPARE
        // Signed and clipped mixed inputs, and enough frames for allpass tails.
        for(integer profile=0;profile<3;profile++) begin
            reset_fx(2'(profile),3'd0);
            repeat(16500) send($random(random_seed)>>>6,$random(random_seed)>>>6,
                $random(random_seed)>>>10,$random(random_seed)>>>10,$random(random_seed)>>>10);
        end
        $display("PASS C1_R04_BIT_EXACT results=%0d",compared);
`endif
        $display("PASS C1_DELAY_CHORUS_SOLO five selections, quiet K2 and K1 changes");
        $display("PASS C1_FX_STEMS echo=5 chorus=5 reverb=5");
        $display("PASS C1_FX frames=%0d chorus_frames=%0d reverb_tail_frames=%0d",id,chorus_seen,reverb_seen);
        $finish;
    end
endmodule
