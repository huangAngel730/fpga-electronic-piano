// M2 pixel-by-pixel oracle using integer geometry from the original renderer.
// Independent of the new constant-interval implementation; simulation only.
`timescale 1ns/1ps
module tb_renderer_geometry_equiv #(
    parameter integer W=640, H=480, N=49, BASE=36,
    parameter integer JUDGE=400, KEY_TOP=410
);
    logic de=1, mode=0, desync=0;
    logic [15:0] x=0, y=0;
    logic [127:0] keys=0;
    logic [7:0] lv=0, sv=0, hit=0, miss=0;
    logic [55:0] ln=0, sn=0;
    logic [79:0] ly=0, le=0, sy=0, st=0, se=0, lvel=0, svel=0;
    wire [23:0] actual;
    integer checks=0;
    integer seed=32'h173049;
    visual_scene_renderer #(.SCREEN_WIDTH(W), .SCREEN_HEIGHT(H),
        .NOTE_COUNT(N), .BASE_NOTE(BASE), .JUDGE_Y(JUDGE),
        .KEYBOARD_TOP(KEY_TOP)) dut (
        .data_enable(de),.pixel_x(x),.pixel_y(y),.display_mode(mode),
        .desync_latched(desync),.key_down(keys),.flash_active(128'd0), .flash_level(256'd0),.live_valid(lv),
        .live_note_number(ln),.live_y(ly),.live_end_y(le),.live_velocity(lvel),
        .score_valid(sv),.score_note_number(sn),.score_y(sy),
        .score_top_y(st),.score_end_y(se),
        .score_velocity(svel),.score_hit(hit),.score_miss(miss),
        .rgb_r(actual[23:16]),.rgb_g(actual[15:8]),.rgb_b(actual[7:0])
    );
    function automatic [23:0] golden;
        integer lane, left_x, right_x, note, pitch, velocity, top_y;
        reg [7:0] r,g,b;
        begin
            r=0;g=0;b=0;
            if(de && int'(x)<W && int'(y)<H) begin
                r=8'h08;g=8'h10;b=8'h20;
                lane=int'(x)*N/W;
                left_x=lane*W/N; right_x=(lane+1)*W/N;
                if(int'(x)==left_x) begin r=8'h18;g=8'h28;b=8'h3c;end
                if(mode && int'(y)==H-1)
                    begin r=8'hf0;g=8'hb0;b=8'h30;end
                // The original draw loop overwrites colors from low to high.
                for(integer slot=0;slot<8;slot=slot+1) begin
                    note=mode ? int'(sn[slot*7+:7]) : int'(ln[slot*7+:7]);
                    left_x=(note-BASE)*W/N;
                    right_x=(note-BASE+1)*W/N;
                    top_y=int'(st[slot*10+:10]);
                    if(note>=BASE && note<BASE+N && int'(x)>left_x &&
                       int'(x)+2<=right_x &&
                       ((!mode && lv[slot] && int'(y)>=int'(ly[slot*10+:10]) &&
                        int'(y)<int'(le[slot*10+:10])) ||
                        (mode && sv[slot] && int'(y)>=top_y && int'(y)<int'(se[slot*10+:10])))) begin
                        velocity=(mode ? int'(svel[slot*10+:10]) :
                                         int'(lvel[slot*10+:10])) >> 2;
                        if(!mode) begin
                            r=48+(velocity>>1);g=112+(velocity>>1);b=160+(velocity>>2);
                        end else if(hit[slot]) begin r=8'h30;g=8'he8;b=8'h70;end
                        else if(miss[slot]) begin r=8'he8;g=8'h38;b=8'h38;end
                        else begin r=112+(velocity>>1);g=72+(velocity>>2);b=176+(velocity>>2);end
                    end
                end
                if(desync && int'(y)<18) begin
                    if(x[4]) begin r=8'hff;g=8'h28;b=8'h28;end
                    else begin r=8'h80;g=8'h08;b=8'h08;end
                end
            end
            golden={r,g,b};
        end
    endfunction
    task automatic compare;
        reg [23:0] expected;
        begin
            #1; expected=golden();
            if(actual!==expected)
                $fatal(1,"RGB x=%0d y=%0d mode=%0d W/N=%0d/%0d got=%h expected=%h",
                       x,y,mode,W,N,actual,expected);
            checks=checks+1;
        end
    endtask
    initial begin
        // All possible X values, with and without key highlighting.
        for(integer ix=0;ix<65536;ix=ix+1) begin
            x=16'(ix);y=16'(KEY_TOP);keys='0;compare();
            keys='1;compare();
        end
        keys=0;
        // Scan every lane against every active X with all 8 slots overlapping.
        // Vary occupied mask, velocity extremes, hit/miss and clipping at y=0.
        for(integer lane=0;lane<N;lane=lane+1) begin
            for(integer slot=0;slot<8;slot=slot+1) begin
                ln[slot*7+:7]=7'(BASE+lane);sn[slot*7+:7]=7'(BASE+lane);
                ly[slot*10+:10]=10'd9;le[slot*10+:10]=10'd31;sy[slot*10+:10]=10'(JUDGE);st[slot*10+:10]=0;se[slot*10+:10]=12;
                lvel[slot*10+:10]=10'(slot*146);svel[slot*10+:10]=10'(1023-slot*146);
            end
            for(integer ix=0;ix<W;ix=ix+1) begin
                x=16'(ix);mode=0;y=9;lv=8'hff;compare();
                mode=1;y=0;sv=8'hff;hit=8'h80;miss=8'hff;compare();
                hit=0;compare();miss=0;compare();
            end
        end
        // Every occupancy mask, highest-slot overwrite and interval endpoints.
        x=1;ln=0;sn=0;
        for(integer slot=0;slot<8;slot=slot+1) begin
            ln[slot*7+:7]=7'(BASE);sn[slot*7+:7]=7'(BASE);
        end
        for(integer mask=0;mask<256;mask=mask+1) begin
            lv=8'(mask);sv=8'(mask);mode=0;y=9;compare();
            mode=1;y=11;compare();y=12;compare();
        end
        // Deterministic random scenes, including all MIDI note numbers,
        // off-screen Y, blanking, all key bits and desync layering.
        for(integer sample=0;sample<20000;sample=sample+1) begin
            x=16'($unsigned($random(seed))%(W+2));
            y=16'($unsigned($random(seed))%(H+2));
            de=$random(seed);mode=$random(seed);desync=$random(seed);
            keys={$random(seed),$random(seed),$random(seed),$random(seed)};
            lv=$random(seed);sv=$random(seed);hit=$random(seed);miss=$random(seed);
            for(integer slot=0;slot<8;slot=slot+1) begin
                ln[slot*7+:7]=$random(seed);sn[slot*7+:7]=$random(seed);
                ly[slot*10+:10]=$random(seed);le[slot*10+:10]=$random(seed);sy[slot*10+:10]=$random(seed);st[slot*10+:10]=$random(seed);se[slot*10+:10]=$random(seed);
                lvel[slot*10+:10]=$random(seed);svel[slot*10+:10]=$random(seed);
            end
            compare();
        end
        $display("PASS renderer geometry W=%0d N=%0d BASE=%0d: %0d RGB comparisons",W,N,BASE,checks);
        $finish;
    end
    initial begin #100_000_000; $fatal(1,"renderer geometry timeout"); end
endmodule
