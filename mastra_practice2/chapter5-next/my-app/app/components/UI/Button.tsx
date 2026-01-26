import { ReactNode } from "react"

type ButtonProps = {
  children: ReactNode;
  onClick: () => void;
  variant?: string;
}

export const Button = ({children, onClick, variant="bg-green-500"}: ButtonProps) => {
  const baseClasses = "px-4 py-2 rounded transitions-colors"
  const variantClasses = variant === 'bg-green-500' ? 'bg-green-500 hover:bg-green-700' : variant;

  return (
    <>
      <button className={`${baseClasses} ${variantClasses}`} onClick={onClick}>
        {children}
      </button>
    </>
  )
}