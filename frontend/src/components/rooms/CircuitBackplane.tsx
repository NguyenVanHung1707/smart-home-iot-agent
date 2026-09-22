type CircuitBackplaneProps = {
  className?: string;
};

const roomHeaderTraces: Array<{ d: string; dots: Array<{ cx: number; cy: number }> }> = [
  {
    d: "M26 88 H198 L226 116 H390",
    dots: [
      { cx: 26, cy: 88 },
      { cx: 390, cy: 116 },
    ],
  },
  {
    d: "M164 144 H302 L334 176 H472",
    dots: [
      { cx: 164, cy: 144 },
      { cx: 472, cy: 176 },
    ],
  },
  {
    d: "M438 88 H610 L642 120 H836",
    dots: [
      { cx: 438, cy: 88 },
      { cx: 836, cy: 120 },
    ],
  },
  {
    d: "M548 162 H714 L748 196 H972",
    dots: [
      { cx: 548, cy: 162 },
      { cx: 972, cy: 196 },
    ],
  },
  {
    d: "M78 204 H242 V224 H414",
    dots: [
      { cx: 78, cy: 204 },
      { cx: 414, cy: 224 },
    ],
  },
  {
    d: "M520 224 H700 V204 H906",
    dots: [
      { cx: 520, cy: 224 },
      { cx: 906, cy: 204 },
    ],
  },
];

const roomBandTraces: Array<{ d: string; dots: Array<{ cx: number; cy: number }> }> = [
  {
    d: "M132 236 V276 H244 L276 308 H382",
    dots: [
      { cx: 132, cy: 236 },
      { cx: 382, cy: 308 },
    ],
  },
  {
    d: "M377 236 V286 H456 L492 322 H598",
    dots: [
      { cx: 377, cy: 236 },
      { cx: 598, cy: 322 },
    ],
  },
  {
    d: "M622 236 V276 H752 L786 308 H918",
    dots: [
      { cx: 622, cy: 236 },
      { cx: 918, cy: 308 },
    ],
  },
  {
    d: "M42 266 H178 L214 302 H360",
    dots: [
      { cx: 42, cy: 266 },
      { cx: 360, cy: 302 },
    ],
  },
  {
    d: "M516 302 H688 L724 266 H958",
    dots: [
      { cx: 516, cy: 302 },
      { cx: 958, cy: 266 },
    ],
  },
  {
    d: "M96 318 H286 L318 350 H500",
    dots: [
      { cx: 96, cy: 318 },
      { cx: 500, cy: 350 },
    ],
  },
  {
    d: "M414 350 H610 L642 318 H914",
    dots: [
      { cx: 414, cy: 350 },
      { cx: 914, cy: 318 },
    ],
  },
  {
    d: "M246 288 H326 V336 H450",
    dots: [
      { cx: 246, cy: 288 },
      { cx: 450, cy: 336 },
    ],
  },
  {
    d: "M548 336 H674 V288 H820",
    dots: [
      { cx: 548, cy: 336 },
      { cx: 820, cy: 288 },
    ],
  },
];

const radiatingTraces: Array<{ d: string; cx: number; cy: number }> = [
  { d: "M514.2 577.9 L661.1 431.0 H969.0", cx: 969.0, cy: 431.0 },
  { d: "M485.8 577.9 L338.9 431.0 H31.0", cx: 31.0, cy: 431.0 },
  { d: "M523.6 581.3 L650.6 454.3 H995.1", cx: 995.1, cy: 454.3 },
  { d: "M476.4 581.3 L349.4 454.3 H4.9", cx: 4.9, cy: 454.3 },
  { d: "M532.2 586.4 L640.9 477.7 H943.8", cx: 943.8, cy: 477.7 },
  { d: "M467.8 586.4 L359.1 477.7 H56.2", cx: 56.2, cy: 477.7 },
  { d: "M539.7 593.0 L631.7 501.0 H984.4", cx: 984.4, cy: 501.0 },
  { d: "M460.3 593.0 L368.3 501.0 H15.6", cx: 15.6, cy: 501.0 },
  { d: "M546.0 600.8 L622.4 524.3 H933.0", cx: 933.0, cy: 524.3 },
  { d: "M454.0 600.8 L377.6 524.3 H67.0", cx: 67.0, cy: 524.3 },
  { d: "M550.7 609.6 L612.6 547.7 H965.0", cx: 965.0, cy: 547.7 },
  { d: "M449.3 609.6 L387.4 547.7 H35.0", cx: 35.0, cy: 547.7 },
  { d: "M553.7 619.1 L601.8 571.0 H993.0", cx: 993.0, cy: 571.0 },
  { d: "M446.3 619.1 L398.2 571.0 H7.0", cx: 7.0, cy: 571.0 },
  { d: "M555.0 629.0 L589.6 594.3 H929.5", cx: 929.5, cy: 594.3 },
  { d: "M445.0 629.0 L410.4 594.3 H70.5", cx: 70.5, cy: 594.3 },
  { d: "M554.4 639.0 L575.7 617.7 H953.0", cx: 953.0, cy: 617.7 },
  { d: "M445.6 639.0 L424.3 617.7 H47.0", cx: 47.0, cy: 617.7 },
  { d: "M552.1 648.7 L559.8 641.0 H969.0", cx: 969.0, cy: 641.0 },
  { d: "M447.9 648.7 L440.2 641.0 H31.0", cx: 31.0, cy: 641.0 },
  { d: "M548.0 657.8 L554.6 664.3 H935.9", cx: 935.9, cy: 664.3 },
  { d: "M452.0 657.8 L445.4 664.3 H64.1", cx: 64.1, cy: 664.3 },
  { d: "M542.4 666.0 L564.0 687.7 H988.8", cx: 988.8, cy: 687.7 },
  { d: "M457.6 666.0 L436.0 687.7 H11.2", cx: 11.2, cy: 687.7 },
  { d: "M535.4 673.1 L573.2 711.0 H964.2", cx: 964.2, cy: 711.0 },
  { d: "M464.6 673.1 L426.8 711.0 H35.8", cx: 35.8, cy: 711.0 },
];

export function CircuitBackplane({ className = "circuit-backplane" }: CircuitBackplaneProps) {
  return (
    <g className={className}>
      <g className="room-header-circuits">
        {roomHeaderTraces.map((trace) => (
          <path key={trace.d} d={trace.d} />
        ))}
        {roomHeaderTraces.flatMap((trace) =>
          trace.dots.map((dot) => (
            <circle key={`${trace.d}-${dot.cx}-${dot.cy}`} cx={dot.cx} cy={dot.cy} r="2.2" />
          )),
        )}
      </g>
      <g className="room-band-circuits">
        {roomBandTraces.map((trace) => (
          <path key={trace.d} d={trace.d} />
        ))}
        {roomBandTraces.flatMap((trace) =>
          trace.dots.map((dot) => (
            <circle key={`${trace.d}-${dot.cx}-${dot.cy}`} cx={dot.cx} cy={dot.cy} r="2.6" />
          )),
        )}
      </g>
      <g className="lower-circuits">
        {radiatingTraces.map((trace) => (
          <path key={trace.d} d={trace.d} />
        ))}
        {radiatingTraces.map((trace) => (
          <circle key={`${trace.cx}-${trace.cy}`} cx={trace.cx} cy={trace.cy} r="2.4" />
        ))}
      </g>
    </g>
  );
}
