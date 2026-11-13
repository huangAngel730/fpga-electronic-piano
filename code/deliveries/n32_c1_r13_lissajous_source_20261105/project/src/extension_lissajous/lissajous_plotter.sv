`timescale 1ns/1ps
// Independent pixel-domain candidate. All inputs synchronous to clk.
// rst_n is synchronous active low. Bitmap contents are never reset.
// Input pixel at edge N -> registered rgb/mask/trace_valid after N+2.
module lissajous_plotter #(
    parameter integer PLOT_BITS = 8,
    parameter integer POINTS_PER_FRAME = 512,
    parameter integer ROI_X = 192,
    parameter integer ROI_Y = 112
) (
    input  logic clk, rst_n, enable, activity,
    input  logic point_restart, point_valid,
    input  logic [7:0] point_x, point_y,
    input  logic [1:0] point_timbre,
    input  logic [11:0] pixel_x, pixel_y,
    input  logic pixel_de, frame_start,
    output logic [23:0] rgb,
    output logic mask, trace_valid,
    output logic [31:0] point_drop_count, published_frames
);
    localparam integer SIDE = 1 << PLOT_BITS;
    localparam integer ADDR_BITS = 2 * PLOT_BITS;
    localparam integer PIXELS = 1 << ADDR_BITS;
    localparam integer COUNT_BITS = (POINTS_PER_FRAME < 2) ? 1 : $clog2(POINTS_PER_FRAME + 1);
    localparam logic [3:0] CLEAR=0, WAIT_POINT=1, LINE_MAGNITUDE=2,
        LINE_SETUP=3, LINE_DRAW=4, LINE_DECIDE=5, LINE_X=6, LINE_Y=7, PENDING=8;
    localparam logic [23:0] BACKGROUND=24'h081020, AXIS=24'h404040;

    logic bitmap0 [0:PIXELS-1] /* synthesis syn_ramstyle = "block_ram" */;
    logic bitmap1 [0:PIXELS-1] /* synthesis syn_ramstyle = "block_ram" */;
    logic [3:0] state;
    logic front_bank, back_bank, front_valid;
    logic [1:0] front_timbre, back_timbre;
    logic [ADDR_BITS-1:0] clear_address;
    logic [COUNT_BITS-1:0] point_count;
    logic have_previous;
    logic enable_q, activity_q;
    logic [PLOT_BITS-1:0] previous_x, previous_y, line_x, line_y, end_x, end_y;
    logic signed [PLOT_BITS:0] delta_x, delta_y;
    logic signed [PLOT_BITS:0] positive_dx, negative_dy;
    logic x_positive, y_positive, step_x, step_y;
    logic signed [PLOT_BITS+1:0] line_error;
    wire signed [PLOT_BITS+2:0] twice_error =
        $signed({line_error[PLOT_BITS+1], line_error}) <<< 1;
    wire gate_change = (enable != enable_q) || (activity != activity_q);
    wire flush = point_restart || gate_change;
    wire in_range = ({1'b0,point_x} < SIDE) && ({1'b0,point_y} < SIDE);
    wire accept_point = rst_n && !flush && enable && activity &&
        state == WAIT_POINT && point_valid && in_range;
    wire first_point = accept_point && !have_previous;
    wire swap_now = rst_n && !flush && enable && activity &&
        state == PENDING && frame_start;
    wire draw_pixel = state == LINE_DRAW && rst_n && !flush && enable && activity;
    wire clear_pixel = state == CLEAR && rst_n && !flush;
    wire [ADDR_BITS-1:0] write_address = clear_pixel ? clear_address :
        first_point ? {point_y[PLOT_BITS-1:0],point_x[PLOT_BITS-1:0]} : {line_y,line_x};
    wire write_enable = clear_pixel || first_point || draw_pixel;
    // Only back_bank is writable. swap_now has no simultaneous write.
    always_ff @(posedge clk) begin
        if(write_enable) begin
            if(back_bank) bitmap1[write_address] <= !clear_pixel;
            else bitmap0[write_address] <= !clear_pixel;
        end
    end

    always_ff @(posedge clk) begin
        if(!rst_n) begin
            state<=CLEAR;front_bank<=0;back_bank<=1;front_valid<=0;
            front_timbre<=0;back_timbre<=0;clear_address<=0;point_count<=0;
            have_previous<=0;enable_q<=0;activity_q<=0;
            previous_x<=0;previous_y<=0;line_x<=0;line_y<=0;end_x<=0;end_y<=0;
            delta_x<=0;delta_y<=0;positive_dx<=0;negative_dy<=0;
            x_positive<=0;y_positive<=0;step_x<=0;step_y<=0;line_error<=0;
            point_drop_count<=0;published_frames<=0;
        end else begin
            enable_q<=enable;activity_q<=activity;
            if(point_valid && !accept_point && point_drop_count!=32'hffffffff)
                point_drop_count<=point_drop_count+1'b1;
            if(flush) begin
                state<=CLEAR;clear_address<=0;point_count<=0;have_previous<=0;
                front_valid<=0;
            end else begin
                case(state)
                    CLEAR:begin
                        if(clear_address==PIXELS-1) begin
                            clear_address<=0;state<=WAIT_POINT;
                        end else clear_address<=clear_address+1'b1;
                    end
                    WAIT_POINT:if(accept_point)begin
                        previous_x<=point_x[PLOT_BITS-1:0];
                        previous_y<=point_y[PLOT_BITS-1:0];
                        point_count<=point_count+1'b1;
                        if(!have_previous) begin
                            have_previous<=1;back_timbre<=point_timbre;
                            if(POINTS_PER_FRAME==1)state<=PENDING;
                        end else begin
                            line_x<=previous_x;line_y<=previous_y;
                            end_x<=point_x[PLOT_BITS-1:0];end_y<=point_y[PLOT_BITS-1:0];
                            delta_x<=$signed({1'b0,point_x[PLOT_BITS-1:0]})-
                                     $signed({1'b0,previous_x});
                            delta_y<=$signed({1'b0,point_y[PLOT_BITS-1:0]})-
                                     $signed({1'b0,previous_y});
                            state<=LINE_MAGNITUDE;
                        end
                    end
                    // Register direction and signed step increments before
                    // the first error sum and reuse them for every pixel.
                    LINE_MAGNITUDE:begin
                        x_positive<=!delta_x[PLOT_BITS];
                        y_positive<=!delta_y[PLOT_BITS];
                        positive_dx<=delta_x[PLOT_BITS] ? -delta_x : delta_x;
                        negative_dy<=delta_y[PLOT_BITS] ? delta_y : -delta_y;
                        state<=LINE_SETUP;
                    end
                    LINE_SETUP:begin
                        line_error<=positive_dx+negative_dy;
                        state<=LINE_DRAW;
                    end
                    LINE_DRAW:begin
                        if(line_x==end_x && line_y==end_y)begin
                            if(point_count==POINTS_PER_FRAME)state<=PENDING;
                            else state<=WAIT_POINT;
                        end else state<=LINE_DECIDE;
                    end
                    LINE_DECIDE:begin
                        step_x<=twice_error>=negative_dy;
                        step_y<=twice_error<=positive_dx;
                        state<=LINE_X;
                    end
                    LINE_X:begin
                        if(step_x)begin
                            line_error<=line_error+negative_dy;
                            line_x<=x_positive ? line_x+1'b1 : line_x-1'b1;
                        end
                        state<=LINE_Y;
                    end
                    LINE_Y:begin
                        if(step_y)begin
                            line_error<=line_error+positive_dx;
                            line_y<=y_positive ? line_y+1'b1 : line_y-1'b1;
                        end
                        state<=LINE_DRAW;
                    end
                    PENDING:if(swap_now)begin
                        front_bank<=back_bank;back_bank<=front_bank;
                        front_valid<=1;front_timbre<=back_timbre;
                        if(published_frames!=32'hffffffff)published_frames<=published_frames+1'b1;
                        state<=CLEAR;clear_address<=0;point_count<=0;have_previous<=0;
                    end
                    default:begin state<=CLEAR;clear_address<=0;front_valid<=0;have_previous<=0;point_count<=0;end
                endcase
            end
        end
    end

    // Stage N: capture local address and the effective front AFTER this edge's
    // possible swap. Stage N+1: synchronous read of both RAM banks. Stage N+2:
    // select registered data and color. No whole-bitmap mux/search exists.
    wire pixel_in_roi = pixel_de && enable && pixel_x>=ROI_X && pixel_x<ROI_X+SIDE &&
        pixel_y>=ROI_Y && pixel_y<ROI_Y+SIDE;
    wire [11:0] local_x = pixel_x-ROI_X;
    wire [11:0] local_y = pixel_y-ROI_Y;
    logic [ADDR_BITS-1:0] read_address;
    logic roi0,roi1,axis0,axis1,bank0,bank1,trace0,trace1;
    logic [1:0] color0,color1;
    logic ram0_q,ram1_q;
    // Deliberately no reset on RAM or its synchronous data registers. Valid
    // metadata prevents uninitialized RAM data from reaching RGB/trace_valid.
    always_ff @(posedge clk) begin
        ram0_q<=bitmap0[read_address];
        ram1_q<=bitmap1[read_address];
    end
    function automatic logic [23:0] trace_color(input logic [1:0] timbre);
        trace_color=(timbre==2'd1) ? 24'hffa030 : 24'h00e0ff;
    endfunction
    wire trajectory_hit = trace1 && (bank1 ? ram1_q : ram0_q);
    always_ff @(posedge clk) begin
        if(!rst_n)begin
            read_address<=0;roi0<=0;roi1<=0;axis0<=0;axis1<=0;
            bank0<=0;bank1<=0;trace0<=0;trace1<=0;color0<=0;color1<=0;
            rgb<=0;mask<=0;trace_valid<=0;
        end else begin
            // Out-of-ROI RAM addresses are harmless. roi0/roi1 mask
            // their output, so the ROI compare never drives the address mux.
            read_address<={local_y[PLOT_BITS-1:0],local_x[PLOT_BITS-1:0]};
            roi0<=pixel_in_roi;
            axis0<=(pixel_x==12'(ROI_X+SIDE/2))||(pixel_y==12'(ROI_Y+SIDE/2-1));
            bank0<=swap_now ? back_bank : front_bank;
            color0<=swap_now ? back_timbre : front_timbre;
            trace0<=!flush && enable && activity && (front_valid || swap_now);
            roi1<=roi0;axis1<=axis0;bank1<=bank0;color1<=color0;
            trace1<=trace0 && !flush && enable && activity;
            mask<=roi1 && enable;
            trace_valid<=roi1 && enable && activity && !flush && trajectory_hit;
            if(!roi1 || !enable)rgb<=0;
            else if(activity && !flush && trajectory_hit)rgb<=trace_color(color1);
            else rgb<=axis1 ? AXIS : BACKGROUND;
        end
    end

    // synthesis translate_off
    initial begin
        if(PLOT_BITS<1 || PLOT_BITS>8 || POINTS_PER_FRAME<1 || ROI_X<0 || ROI_Y<0 ||
           ROI_X+SIDE>4096 || ROI_Y+SIDE>4096)$fatal(1,"invalid lissajous_plotter parameters");
    end
    always @(posedge clk) if(rst_n)begin
        if(front_bank===back_bank)$fatal(1,"front/back banks must differ");
        if(write_enable && back_bank===front_bank)$fatal(1,"attempt to write front bitmap");
    end
    // synthesis translate_on
endmodule
