import { createTheme } from '@mui/material/styles';
import { palette } from './palette';
import { spacing } from './spacing';
import { radius } from './radius';
// import { typography } from './typography';
import { getTypography } from './typography';
// import { createGlobalStyle } from 'styled-components';

// const GlobalStyle = createGlobalStyle`
//   input:-internal-autofill-selected {
//     appearance: none !important;
//     background-image: none !important;
//     background-color: transparent !important;
//     color: inherit !important;
//   }
// `;

const baseTheme = createTheme();
const theme = createTheme({
  ...baseTheme,
  typography: getTypography(baseTheme),
  palette,
  spacing: 8,
  shape: {
    borderRadius: radius.md,
  },
  custom: {
    radius,
    spacing,
    colors: palette,
  },
  components: {
    MuiInputBase: {
      styleOverrides: {
        root: {
          '& input': {
            '&:-webkit-autofill': {
              WebkitBoxShadow: '0 0 0 100px transparent inset !important',
              transition: 'background-color 5000s ease-in-out 0s',
            },
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '&.darkBackground': {
            '& .MuiInputBase-input': {
              color: 'white',
            },
            '& .MuiOutlinedInput-root': {
              '& fieldset': {
                border: '2px solid white',
              },
              '&:hover fieldset': {
                border: '2px solid white',
              },
              '&.Mui-focused fieldset': {
                border: '2px solid white',
              },
              '&.Mui-disabled fieldset': {
                border: '2px solid #999999',
                color: '#999999',
              },
            },
            '& .MuiInputBase-input.Mui-disabled': {
              WebkitTextFillColor: '#999999',
            },
            '& input': {
              '&:-webkit-autofill': {
                WebkitBoxShadow: '0 0 0 100px transparent inset !important',
                WebkitTextFillColor: 'white !important',
                transition: 'background-color 5000s ease-in-out 0s',
              },
              '&:-webkit-autofill:hover': {
                WebkitBoxShadow: '0 0 0 100px transparent inset !important',
                WebkitTextFillColor: 'white !important',
              },
              '&:-webkit-autofill:focus': {
                WebkitBoxShadow: '0 0 0 100px transparent inset !important',
                WebkitTextFillColor: 'white !important',
              },
            },
            '& .MuiInputLabel-root': {
              color: 'white',
            },
            '& .MuiInputLabel-root.Mui-focused': {
              color: 'white',
            },
            '& .MuiInputLabel-root.Mui-disabled': {
              color: '#999999',
            },
          },
          '&.lightBackground': {
            '& .MuiInputBase-input': {
              color: '#000000a3',
            },
            '& .MuiOutlinedInput-root': {
              '& fieldset': {
                border: '2px solid #00000026',
              },
              '&:hover fieldset': {
                border: '2px solid #00000026',
              },
              '&.Mui-focused fieldset': {
                border: '2px solid #00000026',
              },
              '&.Mui-disabled fieldset': {
                border: '2px solid #999999',
                color: '#999999',
              },
            },
            '& .MuiInputBase-input.Mui-disabled': {
              WebkitTextFillColor: '#999999',
            },
            '& input': {
              '&:-webkit-autofill': {
                WebkitBoxShadow: '0 0 0 100px transparent inset !important',
                WebkitTextFillColor: '#00000026 !important',
                transition: 'background-color 5000s ease-in-out 0s',
              },
              '&:-webkit-autofill:hover': {
                WebkitBoxShadow: '0 0 0 100px transparent inset !important',
                WebkitTextFillColor: '#00000026 !important',
              },
              '&:-webkit-autofill:focus': {
                WebkitBoxShadow: '0 0 0 100px transparent inset !important',
                WebkitTextFillColor: '#00000026 !important',
              },
            },
            '& .MuiInputLabel-root': {
              color: '#00000026',
            },
            '& .MuiInputLabel-root.Mui-focused': {
              color: '#00000026',
            },
            '& .MuiInputLabel-root.Mui-disabled': {
              color: '#999999',
            },
          },
        },
      },
    },
    MuiAccordion: {
      variants: [
        {
          props: { variant: 'transparent' },
          style: {
            backgroundColor: 'transparent',
            boxShadow: 'none',
            '&:before': {
              display: 'none',
            },
            borderColor: 'white',
            borderStyle: 'solid',
            borderWidth: '1px', // '1' should be '1px'
          },
        },
      ],
    },
    MuiAccordionSummary: {
      variants: [
        {
          props: { variant: 'transparent' },
          style: {
            backgroundColor: 'transparent',
            minHeight: 'auto',
            '& .MuiAccordionSummary-content': {
              margin: 0,
            },
            '& .MuiAccordionSummary-expandIconWrapper': {
              color: 'white',
            },
          },
        },
      ],
    },
    MuiAccordionDetails: {
      variants: [
        {
          props: { variant: 'transparent' },
          style: {
            backgroundColor: 'transparent',
          },
        },
      ],
    },
    // MuiButton: {
    //   styleOverrides: {
    //     root: {
    //       borderRadius: 8,
    //       fontWeight: 600,
    //       fontSize: '16px',
    //       lineHeight: '24px',
    //       textTransform: 'none',
    //       padding: '6px 16px',
    //       transition: 'all 0.2s ease-in-out',
    //       '&.Mui-disabled': {
    //         backgroundColor: '#f2f2f2',
    //         color: '#8c8c8c',
    //       },
    //     },
    //     containedPrimary: {
    //       backgroundColor: '#995a00',
    //       color: '#ffffff',
    //       '&:hover': {
    //         backgroundColor: '#bf7000',
    //       },
    //     },
    //     outlinedPrimary: {
    //       color: '#995a00',
    //       border: '2px solid rgba(153, 90, 0, 0.5)',
    //       '&:hover': {
    //         backgroundColor: 'rgba(153, 90, 0, 0.05)',
    //       },
    //     },
    //     textPrimary: {
    //       color: '#995a00',
    //       '&:hover': {
    //         backgroundColor: 'rgba(153, 90, 0, 0.05)',
    //       },
    //     },
    //   },
    // }
  },
});

export default theme;
