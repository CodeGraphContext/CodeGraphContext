import React from 'react';

export interface SampleProps {
  title: string;
}

export const SampleComponent: React.FC<SampleProps> = ({ title }) => {
  return <div>{title}</div>;
};

export function helperFunction(x: number): number {
  return x * 2;
}

export default SampleComponent;
